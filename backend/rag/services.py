"""
The RAG pipeline for resumes: chunk -> embed -> store in ChromaDB -> retrieve.

Public functions other Django apps (Resume Expert, AI Interviewer, Career
Coach, AI Tutor, ...) should use:

    from rag.services import retrieve_relevant_chunks
    chunks = retrieve_relevant_chunks(user, "What backend frameworks have they used?")

`retrieve_relevant_chunks` is the only entry point those modules need — it
indexes the user's resume on first use if it isn't indexed yet, so callers
never have to think about indexing state themselves.

Module 8 note: chunking, storage, retrieval, indexing state, and isolation
all still live here, unchanged from Module 4 — none of that moved. Only the
raw "call Gemini for an embedding" step now goes through the FastAPI AI
service (see embed_texts below) instead of calling the google-genai SDK
directly in this process.
"""

import hashlib
from typing import List

import chromadb
from django.conf import settings
from django.utils import timezone

from ai_client.client import AIServiceHTTPError, post as ai_service_post
from resumes.models import Resume

from .models import ResumeIndex

CHUNK_SIZE_WORDS = 200
CHUNK_OVERLAP_WORDS = 40


class RAGError(Exception):
    """Raised for embedding/storage failures. Never raised for "just no data yet"."""


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------
def chunk_text(text: str, chunk_size: int = CHUNK_SIZE_WORDS, overlap: int = CHUNK_OVERLAP_WORDS) -> List[str]:
    """Splits text into overlapping word-count chunks. Simple by design —
    good enough for resume-length documents without pulling in a heavier
    text-splitting library."""
    words = text.split()
    if not words:
        return []

    chunks = []
    step = max(chunk_size - overlap, 1)
    for start in range(0, len(words), step):
        chunk_words = words[start : start + chunk_size]
        if chunk_words:
            chunks.append(" ".join(chunk_words))
        if start + chunk_size >= len(words):
            break
    return chunks


# ---------------------------------------------------------------------------
# Embeddings — Module 8: the actual Gemini call now lives in the FastAPI AI
# service; this just sends the text(s) over and unwraps the response. The
# function's signature, return shape, and RAGError-on-failure contract are
# unchanged, so callers (index_resume, retrieve_relevant_chunks below) and
# every existing test that mocks `embed_texts` directly are unaffected.
# ---------------------------------------------------------------------------
def embed_texts(texts: List[str], task_type: str) -> List[List[float]]:
    """task_type is 'RETRIEVAL_DOCUMENT' when embedding resume chunks to
    store, or 'RETRIEVAL_QUERY' when embedding a search query — Gemini's
    embedding model produces better-aligned vectors when it knows which
    side of the search a given piece of text is on."""
    if not texts:
        return []
    try:
        data = ai_service_post("/embeddings", {"texts": texts, "task_type": task_type})
    except AIServiceHTTPError as exc:
        raise RAGError(f"Embedding request failed: {exc}") from exc

    embeddings = data.get("embeddings")
    if not embeddings:
        raise RAGError("Embedding request returned no vectors.")
    return embeddings


# ---------------------------------------------------------------------------
# ChromaDB
# ---------------------------------------------------------------------------
_chroma_client = None


def get_chroma_collection():
    """A single shared collection, isolated per user/resume purely via
    metadata filtering (see index_resume / retrieve_relevant_chunks below) —
    simpler to operate than one collection per user, at this data volume.

    Module 8: when CHROMA_HTTP_HOST is set (the docker-compose / Render
    setup, where Chroma runs as its own containerized server), connects to
    it over HTTP. Otherwise falls back to the local-directory PersistentClient
    from Module 4 — unchanged default for plain local development."""
    global _chroma_client
    if _chroma_client is None:
        if settings.CHROMA_HTTP_HOST:
            _chroma_client = chromadb.HttpClient(
                host=settings.CHROMA_HTTP_HOST, port=settings.CHROMA_HTTP_PORT
            )
        else:
            _chroma_client = chromadb.PersistentClient(path=str(settings.CHROMA_PERSIST_DIR))
    return _chroma_client.get_or_create_collection(name=settings.CHROMA_COLLECTION_NAME)


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------
def index_resume(resume: Resume) -> ResumeIndex:
    """Chunks + embeds + stores resume.extracted_text in ChromaDB.
    Idempotent: if this exact text is already indexed, does nothing and
    returns the existing record — this is what prevents duplicate indexing
    on repeated calls (from the signal, a lazy retrieval check, or the
    backfill command all potentially touching the same resume)."""
    text = resume.extracted_text or ""
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    existing = ResumeIndex.objects.filter(resume=resume).first()
    if existing and existing.status == ResumeIndex.STATUS_INDEXED and existing.content_hash == content_hash:
        return existing

    chunks = chunk_text(text)
    if not chunks:
        raise RAGError("Resume has no extracted text to index.")

    try:
        embeddings = embed_texts(chunks, task_type="RETRIEVAL_DOCUMENT")
        collection = get_chroma_collection()
        ids = [f"resume-{resume.id}-chunk-{i}" for i in range(len(chunks))]
        metadatas = [
            {"user_id": resume.user_id, "resume_id": resume.id, "chunk_index": i} for i in range(len(chunks))
        ]
        # upsert (not add) by deterministic ID — re-running this for the same
        # resume overwrites the same chunk IDs instead of duplicating them.
        collection.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=chunks)
    except RAGError as exc:
        ResumeIndex.objects.update_or_create(
            resume=resume,
            defaults={"status": ResumeIndex.STATUS_FAILED, "error_message": str(exc)},
        )
        raise
    except Exception as exc:
        ResumeIndex.objects.update_or_create(
            resume=resume,
            defaults={"status": ResumeIndex.STATUS_FAILED, "error_message": str(exc)},
        )
        raise RAGError(f"Indexing failed: {exc}") from exc

    index_record, _ = ResumeIndex.objects.update_or_create(
        resume=resume,
        defaults={
            "status": ResumeIndex.STATUS_INDEXED,
            "chunk_count": len(chunks),
            "content_hash": content_hash,
            "indexed_at": timezone.now(),
            "error_message": "",
        },
    )
    return index_record


# ---------------------------------------------------------------------------
# Retrieval — the function every future module (Resume Expert, AI
# Interviewer, Career Coach, AI Tutor) should call.
# ---------------------------------------------------------------------------
def retrieve_relevant_chunks(user, query: str, top_k: int = 5) -> List[str]:
    """Returns up to top_k resume-text chunks most relevant to `query`, for
    this user's own resume only. Returns [] if the user has no resume — this
    is a normal, non-error state callers should just treat as "no context
    available" rather than something to catch.

    Isolation is enforced twice: once via ChromaDB's `where` filter, and
    again in Python on the results — a resume/user ID mismatch is treated as
    a bug worth failing loudly on, not something to silently filter past.
    """
    resume = Resume.objects.filter(user=user).first()
    if not resume or resume.status != Resume.STATUS_PROCESSED:
        return []

    # Index lazily if this resume was never indexed (e.g. it existed before
    # this module was added) or its stored content_hash is stale.
    content_hash = hashlib.sha256((resume.extracted_text or "").encode("utf-8")).hexdigest()
    index_record = ResumeIndex.objects.filter(resume=resume).first()
    if not index_record or index_record.status != ResumeIndex.STATUS_INDEXED or index_record.content_hash != content_hash:
        index_resume(resume)  # raises RAGError on failure; caller decides how to handle

    if not query or not query.strip():
        return []

    query_embedding = embed_texts([query], task_type="RETRIEVAL_QUERY")[0]
    collection = get_chroma_collection()
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where={"$and": [{"user_id": user.id}, {"resume_id": resume.id}]},
    )

    documents = (results.get("documents") or [[]])[0]
    metadatas = (results.get("metadatas") or [[]])[0]

    safe_chunks = []
    for doc, meta in zip(documents, metadatas):
        if meta.get("user_id") != user.id or meta.get("resume_id") != resume.id:
            # Should be impossible given the `where` filter above, but a
            # cross-user leak is exactly the kind of bug we never swallow.
            raise RAGError("Retrieved a chunk that did not match the requesting user's resume.")
        safe_chunks.append(doc)

    return safe_chunks
