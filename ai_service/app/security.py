from fastapi import Header, HTTPException, status

from .config import settings


def verify_internal_key(x_internal_api_key: str = Header(default="")):
    """Every router except /health depends on this. If AI_SERVICE_INTERNAL_KEY
    isn't set, the check is skipped (local dev convenience) — but Django
    only ever sends this service requests from inside a private network
    (docker-compose's internal network, or Render's private networking), so
    this is a secondary safety net, not the only thing standing between the
    public internet and this service."""
    if not settings.internal_api_key:
        return
    if x_internal_api_key != settings.internal_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing internal API key.",
        )
