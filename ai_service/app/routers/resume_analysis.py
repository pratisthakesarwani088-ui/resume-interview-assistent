from fastapi import APIRouter, Depends, HTTPException, status

from .. import gemini
from ..schemas import PromptRequest, ResumeAnalysisResponse
from ..security import verify_internal_key

router = APIRouter(dependencies=[Depends(verify_internal_key)])


@router.post("/resume-analysis", response_model=ResumeAnalysisResponse)
def resume_analysis(payload: PromptRequest):
    try:
        result = gemini.generate_structured(payload.prompt, ResumeAnalysisResponse)
    except gemini.GeminiError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return result
