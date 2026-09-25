"""
Analyzes resume text and returns a structured result.

Module 8: the actual Gemini call now lives in the FastAPI AI service —
this module still owns the prompt template and the Pydantic response shape
(so `analysis/views.py` gets back the same typed object it always has),
it just sends the fully-formatted prompt to the AI service instead of
calling the google-genai SDK directly in this process.
"""

from typing import List

from pydantic import BaseModel, Field, ValidationError

from ai_client.client import AIServiceHTTPError, post as ai_service_post

# Resumes can be long; this keeps token usage (and cost) bounded without
# meaningfully hurting analysis quality — a resume's substance is front-loaded.
MAX_RESUME_CHARS = 20000


class AnalysisError(Exception):
    """Raised for any AI-service/config failure the view should treat as a 502."""


class SuggestedRole(BaseModel):
    role: str = Field(description="A specific, realistic job title suited to this resume.")
    required_skills: List[str] = Field(
        description="Key skills typically required for this role (5-8 items)."
    )
    missing_skills: List[str] = Field(
        description="Skills required for this role that are absent from the resume. Empty list if none."
    )


class ResumeAnalysisResult(BaseModel):
    ats_score: int = Field(
        ge=0, le=100, description="Estimated ATS (Applicant Tracking System) compatibility score."
    )
    strengths: List[str] = Field(description="Concrete strengths of this resume (3-6 items).")
    weaknesses: List[str] = Field(description="Concrete weaknesses of this resume (3-6 items).")
    extracted_skills: List[str] = Field(
        description="Technical and general skills found in the resume."
    )
    projects_experience: List[str] = Field(
        description="Notable projects and relevant experience, one short entry each."
    )
    suggested_roles: List[SuggestedRole] = Field(
        description="2-4 job roles this resume is a realistic fit for."
    )
    improvement_suggestions: List[str] = Field(
        description="Concise, actionable suggestions to improve the resume (3-6 items)."
    )


PROMPT_TEMPLATE = """You are an ATS (Applicant Tracking System) and resume analysis expert.

Analyze the resume text below and return a structured assessment. Be specific
and grounded in what's actually written — don't invent details that aren't
there. The ATS score is an estimate of how well the resume would parse and
rank in a typical ATS, not a guarantee of any real system's behavior.

Resume text:
---
{resume_text}
---
"""


def analyze_resume_text(resume_text: str) -> ResumeAnalysisResult:
    """Runs the analysis via the AI service and returns a validated
    ResumeAnalysisResult. Raises AnalysisError on any configuration,
    network, or unexpected-response failure — same contract as before."""

    prompt = PROMPT_TEMPLATE.format(resume_text=resume_text[:MAX_RESUME_CHARS])

    try:
        data = ai_service_post("/resume-analysis", {"prompt": prompt})
    except AIServiceHTTPError as exc:
        raise AnalysisError(f"AI service request failed: {exc}") from exc

    try:
        return ResumeAnalysisResult(**data)
    except ValidationError as exc:
        raise AnalysisError(f"AI service returned a response that didn't match the expected format: {exc}") from exc
