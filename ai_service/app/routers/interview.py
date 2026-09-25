from fastapi import APIRouter, Depends, HTTPException, status

from .. import gemini
from ..schemas import AnswerEvaluationResponse, FinalReportResponse, GeneratedQuestionsResponse, PromptRequest
from ..security import verify_internal_key

router = APIRouter(dependencies=[Depends(verify_internal_key)])


@router.post("/interview/questions", response_model=GeneratedQuestionsResponse)
def interview_questions(payload: PromptRequest):
    try:
        result = gemini.generate_structured(payload.prompt, GeneratedQuestionsResponse)
    except gemini.GeminiError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return result


@router.post("/interview/evaluate", response_model=AnswerEvaluationResponse)
def interview_evaluate(payload: PromptRequest):
    try:
        result = gemini.generate_structured(payload.prompt, AnswerEvaluationResponse)
    except gemini.GeminiError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return result


@router.post("/interview/report", response_model=FinalReportResponse)
def interview_report(payload: PromptRequest):
    try:
        result = gemini.generate_structured(payload.prompt, FinalReportResponse)
    except gemini.GeminiError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return result
