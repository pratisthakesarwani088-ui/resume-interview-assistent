"""
The only module in this entire system (Django + FastAPI) that imports and
calls the google-genai SDK. Everything else — Django's analysis/assistant/
rag services, and every other FastAPI router — goes through the functions
below (via the routers in ./routers/), never touches `genai` directly.

Uses the current `google-genai` SDK (the older `google-generativeai`
package is deprecated/archived).
"""

from typing import List

from google import genai
from google.genai.types import EmbedContentConfig, GenerateContentConfig

from .config import settings


class GeminiError(Exception):
    """Raised for any Gemini configuration/API failure. Routers turn this into a 502."""


_client: genai.Client | None = None


def get_client() -> genai.Client:
    if not settings.gemini_api_key:
        raise GeminiError("GEMINI_API_KEY is not configured on the AI service.")
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def generate_text(system_instruction: str, history: List[dict], message: str) -> str:
    """Free-form chat reply. `history` is prior turns as
    [{"role": "user"|"assistant", "content": str}, ...] — translated here
    into Gemini's own "user"/"model" role naming."""
    client = get_client()
    contents = []
    for turn in history:
        role = "model" if turn.get("role") == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": turn.get("content", "")}]})
    contents.append({"role": "user", "parts": [{"text": message}]})

    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=contents,
            config=GenerateContentConfig(system_instruction=system_instruction),
        )
    except Exception as exc:  # the SDK raises several distinct error types
        raise GeminiError(f"Gemini chat request failed: {exc}") from exc

    text = getattr(response, "text", None)
    if not text:
        raise GeminiError("Gemini returned an empty reply.")
    return text


def generate_structured(prompt: str, schema):
    """Calls Gemini with a Pydantic response_schema so it's constrained to
    return exactly that shape — no manual JSON parsing or prompt-hoping."""
    client = get_client()
    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config={"response_mime_type": "application/json", "response_schema": schema},
        )
    except Exception as exc:
        raise GeminiError(f"Gemini request failed: {exc}") from exc

    result = getattr(response, "parsed", None)
    if result is None:
        raise GeminiError("Gemini returned a response that didn't match the expected format.")
    return result


def embed_texts(texts: List[str], task_type: str) -> List[List[float]]:
    """task_type is 'RETRIEVAL_DOCUMENT' when embedding resume chunks to
    store, or 'RETRIEVAL_QUERY' when embedding a search query."""
    if not texts:
        return []
    client = get_client()
    try:
        response = client.models.embed_content(
            model=settings.gemini_embedding_model,
            contents=texts,
            config=EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=settings.gemini_embedding_dimensions,
            ),
        )
    except Exception as exc:
        raise GeminiError(f"Embedding request failed: {exc}") from exc

    embeddings = getattr(response, "embeddings", None)
    if not embeddings:
        raise GeminiError("Embedding request returned no vectors.")
    return [e.values for e in embeddings]
