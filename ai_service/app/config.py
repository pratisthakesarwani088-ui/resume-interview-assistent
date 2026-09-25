import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    gemini_api_key: str = os.environ.get("GEMINI_API_KEY", "")
    gemini_model: str = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    gemini_embedding_model: str = os.environ.get("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
    # 768/1536/3072 are Google's recommended dimensions for this model
    # (Matryoshka Representation Learning) — 768 keeps storage/query cost
    # down with minimal quality loss for a resume-length corpus.
    gemini_embedding_dimensions: int = int(os.environ.get("GEMINI_EMBEDDING_DIMENSIONS", "768"))
    # Shared secret Django sends as X-Internal-Api-Key. Empty = no auth
    # check (local dev convenience only — always set this in docker-compose
    # and on Render).
    internal_api_key: str = os.environ.get("AI_SERVICE_INTERNAL_KEY", "")


settings = Settings()
