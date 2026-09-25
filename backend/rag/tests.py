import hashlib
import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings, skipUnlessDBFeature

import rag.services as rag_services
from rag.models import ResumeIndex
from rag.services import RAGError, chunk_text, index_resume, retrieve_relevant_chunks
from resumes.models import Resume

User = get_user_model()


def fake_embed(texts, task_type):
    """Deterministic, cheap stand-in for the AI service's embed_texts —
    16-dimensional so it's a realistic-shaped drop-in, but the values
    themselves carry no real semantic meaning (that would need a live
    Gemini call via the AI service, which these unit tests intentionally
    avoid — see Module 8's ai_client/client.py for that boundary)."""
    vectors = []
    for text in texts:
        seed = int(hashlib.sha256(text.encode()).hexdigest(), 16)
        vectors.append([((seed >> (i % 64)) % 1000) / 1000.0 for i in range(16)])
    return vectors


class RAGTestCase(TestCase):
    """Points ChromaDB at a fresh temp directory per test class and resets
    the module-level client cache, so tests never touch real persisted data
    and don't leak state between runs."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._chroma_dir = tempfile.mkdtemp(prefix="rag_test_chroma_")
        cls._settings_override = override_settings(
            CHROMA_PERSIST_DIR=cls._chroma_dir,
            CHROMA_COLLECTION_NAME="test_resume_chunks",
        )
        cls._settings_override.enable()
        rag_services._chroma_client = None

    @classmethod
    def tearDownClass(cls):
        rag_services._chroma_client = None
        shutil.rmtree(cls._chroma_dir, ignore_errors=True)
        cls._settings_override.disable()
        super().tearDownClass()

    def _create_processed_resume(self, user, text):
        return Resume.objects.create(
            user=user,
            file=ContentFile(b"%PDF-1.4 fake", name="resume.pdf"),
            original_filename="resume.pdf",
            file_size=13,
            extracted_text=text,
            page_count=1,
            status=Resume.STATUS_PROCESSED,
        )


class ChunkTextTests(TestCase):
    def test_empty_text_returns_no_chunks(self):
        self.assertEqual(chunk_text(""), [])

    def test_short_text_returns_single_chunk(self):
        text = "Experienced Python developer with Django background."
        chunks = chunk_text(text, chunk_size=200, overlap=40)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], text)

    def test_long_text_splits_into_overlapping_chunks(self):
        words = [f"word{i}" for i in range(500)]
        text = " ".join(words)
        chunks = chunk_text(text, chunk_size=200, overlap=40)
        self.assertGreater(len(chunks), 1)
        # every word should show up somewhere across the chunks
        covered = set(" ".join(chunks).split())
        self.assertEqual(covered, set(words))


class IndexResumeTests(RAGTestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="cand@example.com", name="Candidate", password="StrongPass123")

    @patch.object(rag_services, "embed_texts", side_effect=fake_embed)
    def test_index_resume_creates_chunks_with_metadata(self, mock_embed):
        resume = self._create_processed_resume(
            self.user, "Backend developer skilled in Python, Django, and PostgreSQL. " * 20
        )
        index_record = index_resume(resume)

        self.assertEqual(index_record.status, ResumeIndex.STATUS_INDEXED)
        self.assertGreater(index_record.chunk_count, 0)

        collection = rag_services.get_chroma_collection()
        stored = collection.get(where={"resume_id": resume.id})
        self.assertEqual(len(stored["ids"]), index_record.chunk_count)
        for meta in stored["metadatas"]:
            self.assertEqual(meta["user_id"], self.user.id)
            self.assertEqual(meta["resume_id"], resume.id)

    @patch.object(rag_services, "embed_texts", side_effect=fake_embed)
    def test_reindexing_same_content_is_a_no_op(self, mock_embed):
        resume = self._create_processed_resume(self.user, "Some resume text about Python and Django.")
        index_resume(resume)
        self.assertEqual(mock_embed.call_count, 1)

        index_resume(resume)  # same content_hash -> should skip entirely
        self.assertEqual(mock_embed.call_count, 1)

        collection = rag_services.get_chroma_collection()
        stored = collection.get(where={"resume_id": resume.id})
        self.assertEqual(len(stored["ids"]), len(set(stored["ids"])))  # no duplicate IDs

    @patch.object(rag_services, "embed_texts", side_effect=RAGError("boom"))
    def test_embedding_failure_marks_index_failed_without_raising_past_the_view_layer(self, mock_embed):
        resume = self._create_processed_resume(self.user, "Some resume text.")
        with self.assertRaises(RAGError):
            index_resume(resume)
        record = ResumeIndex.objects.get(resume=resume)
        self.assertEqual(record.status, ResumeIndex.STATUS_FAILED)


class RetrieveRelevantChunksTests(RAGTestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(email="a@example.com", name="User A", password="StrongPass123")
        self.user_b = User.objects.create_user(email="b@example.com", name="User B", password="StrongPass123")

    def test_no_resume_returns_empty_list(self):
        self.assertEqual(retrieve_relevant_chunks(self.user_a, "any query"), [])

    @patch.object(rag_services, "embed_texts", side_effect=fake_embed)
    def test_retrieval_only_returns_own_resume_chunks(self, mock_embed):
        resume_a = self._create_processed_resume(
            self.user_a, "Python Django backend engineer with REST API experience. " * 20
        )
        resume_b = self._create_processed_resume(
            self.user_b, "Frontend engineer skilled in React and TypeScript. " * 20
        )
        index_resume(resume_a)
        index_resume(resume_b)

        results_a = retrieve_relevant_chunks(self.user_a, "backend experience", top_k=10)
        self.assertGreater(len(results_a), 0)
        for chunk in results_a:
            self.assertNotIn("React", chunk)
            self.assertNotIn("TypeScript", chunk)

        results_b = retrieve_relevant_chunks(self.user_b, "backend experience", top_k=10)
        for chunk in results_b:
            self.assertNotIn("Django", chunk)

    @patch.object(rag_services, "embed_texts", side_effect=fake_embed)
    def test_retrieval_lazily_indexes_a_pre_existing_unindexed_resume(self, mock_embed):
        # Simulate a resume that predates this module: processed, but no
        # ResumeIndex row at all (the signal never fired for it).
        resume = self._create_processed_resume(self.user_a, "Data engineer with Python and SQL experience. " * 20)
        ResumeIndex.objects.filter(resume=resume).delete()
        self.assertFalse(ResumeIndex.objects.filter(resume=resume).exists())

        results = retrieve_relevant_chunks(self.user_a, "data engineering", top_k=5)
        self.assertGreater(len(results), 0)
        self.assertTrue(ResumeIndex.objects.filter(resume=resume, status=ResumeIndex.STATUS_INDEXED).exists())


class AutoIndexSignalTests(RAGTestCase):
    @patch.object(rag_services, "embed_texts", side_effect=fake_embed)
    def test_resume_is_indexed_automatically_when_marked_processed(self, mock_embed):
        user = User.objects.create_user(email="signal@example.com", name="Signal User", password="StrongPass123")
        resume = Resume.objects.create(
            user=user,
            file=ContentFile(b"%PDF-1.4 fake", name="resume.pdf"),
            original_filename="resume.pdf",
            file_size=13,
            status=Resume.STATUS_PENDING,
        )
        self.assertFalse(ResumeIndex.objects.filter(resume=resume).exists())

        # This mirrors what Module 2's upload view does after extraction —
        # saving the resume as processed. The signal (not this test) triggers indexing.
        resume.extracted_text = "Full-stack developer with Python, Django, and React experience."
        resume.status = Resume.STATUS_PROCESSED
        resume.save(update_fields=["extracted_text", "status"])

        self.assertTrue(ResumeIndex.objects.filter(resume=resume, status=ResumeIndex.STATUS_INDEXED).exists())
