from fastapi import APIRouter, Depends, HTTPException, status

from .. import gemini
from ..schemas import ChatRequest, ChatResponse
from ..security import verify_internal_key

router = APIRouter(dependencies=[Depends(verify_internal_key)])


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    try:
        reply = gemini.generate_text(
            payload.system_instruction,
            [turn.model_dump() for turn in payload.history],
            payload.message,
        )
    except gemini.GeminiError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return {"reply": reply}
