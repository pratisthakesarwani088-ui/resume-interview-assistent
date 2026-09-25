from typing import List

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str


# ---------------------------------------------------------------------------
# /chat
# ---------------------------------------------------------------------------
class ChatHistoryTurn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    system_instruction: str
    history: List[ChatHistoryTurn] = Field(default_factory=list)
    message: str


class ChatResponse(BaseModel):
    reply: str


# ---------------------------------------------------------------------------
# /embeddings
# ---------------------------------------------------------------------------
class EmbeddingsRequest(BaseModel):
    texts: List[str]
    task_type: str = "RETRIEVAL_DOCUMENT"


class EmbeddingsResponse(BaseModel):
    embeddings: List[List[float]]


# ---------------------------------------------------------------------------
# Structured endpoints all take a single pre-formatted prompt — prompt
# wording/grounding stays owned by Django (see assistant/services.py and
# analysis/services.py); this service only enforces the response shape.
# ---------------------------------------------------------------------------
class PromptRequest(BaseModel):
    prompt: str


class SuggestedRole(BaseModel):
    role: str = Field(description="A specific, realistic job title suited to this resume.")
    required_skills: List[str] = Field(description="Key skills typically required for this role (5-8 items).")
    missing_skills: List[str] = Field(
        description="Skills required for this role that are absent from the resume. Empty list if none."
    )


class ResumeAnalysisResponse(BaseModel):
    ats_score: int = Field(ge=0, le=100, description="Estimated ATS compatibility score.")
    strengths: List[str] = Field(description="Concrete strengths of this resume (3-6 items).")
    weaknesses: List[str] = Field(description="Concrete weaknesses of this resume (3-6 items).")
    extracted_skills: List[str] = Field(description="Technical and general skills found in the resume.")
    projects_experience: List[str] = Field(description="Notable projects and relevant experience.")
    suggested_roles: List[SuggestedRole] = Field(description="2-4 job roles this resume is a realistic fit for.")
    improvement_suggestions: List[str] = Field(description="Concise, actionable suggestions (3-6 items).")


class GeneratedQuestionsResponse(BaseModel):
    questions: List[str] = Field(
        min_length=10,
        max_length=15,
        description="Theory-only interview questions tailored to the role and resume.",
    )


class AnswerEvaluationResponse(BaseModel):
    score: int = Field(ge=0, le=10, description="Score out of 10 for this single answer.")
    feedback: str = Field(description="Concise, specific feedback (2-4 sentences).")
    ideal_answer: str = Field(description="A concise model answer to this question.")


class FinalReportResponse(BaseModel):
    overall_score: int = Field(ge=0, le=100, description="Overall interview performance, 0-100.")
    strengths: List[str] = Field(description="3-6 concrete strengths shown across the interview.")
    weak_areas: List[str] = Field(description="3-6 concrete areas that need improvement.")
    feedback: str = Field(description="A short overall narrative summary (3-5 sentences).")
