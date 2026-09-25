from fastapi import APIRouter, Depends, HTTPException, status

from .. import gemini
from ..schemas import EmbeddingsRequest, EmbeddingsResponse
from ..security import verify_internal_key

router = APIRouter(dependencies=[Depends(verify_internal_key)])


@router.post("/embeddings", response_model=EmbeddingsResponse)
def embeddings(payload: EmbeddingsRequest):
    try:
        vectors = gemini.embed_texts(payload.texts, payload.task_type)
    except gemini.GeminiError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return {"embeddings": vectors}
