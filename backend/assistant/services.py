"""
One reusable service for all four assistant modes: Resume Expert, AI
Interviewer, Career Coach, and AI Tutor. Every mode goes through the same
grounding helper and the same two low-level call primitives (_chat for
free-form replies, the three interview methods for JSON-schema-constrained
output) — there is exactly one place in Django that talks to the AI service.

Module 8: the actual Gemini calls now live in the FastAPI AI service (see
ai_client/client.py for the HTTP layer). This module still owns every
prompt and system-instruction string — prompt wording is a product/business
concern, not infrastructure, so it stays here where it's version-controlled
alongside the grounding logic that feeds it. FastAPI's job is just "call
Gemini with this text, enforce this response shape."

Views should only ever call the public methods on the `ai_assistant`
singleton at the bottom of this file.
"""

from typing import List

from pydantic import BaseModel, Field, ValidationError

from ai_client.client import AIServiceHTTPError, post as ai_service_post
from analysis.models import ResumeAnalysis
from rag.services import RAGError, retrieve_relevant_chunks
from resumes.models import Resume

# How many prior turns (user + assistant messages combined) to send as
# context. Capped to keep latency/cost bounded — plenty for natural
# follow-ups without re-sending an ever-growing transcript.
MAX_HISTORY_MESSAGES = 20


class AIServiceError(Exception):
    """Raised for any AI-service configuration/API failure. Views turn this into a 502."""


class ChatMessageRole:
    """Local string constants, to avoid assistant.services importing
    assistant.models just for two literals."""

    USER = "user"
    ASSISTANT = "assistant"


# ---------------------------------------------------------------------------
# Structured output schemas (interview generation / evaluation / report)
# ---------------------------------------------------------------------------
class GeneratedQuestions(BaseModel):
    questions: List[str] = Field(
        min_length=10,
        max_length=15,
        description="Theory-only interview questions tailored to the role and resume.",
    )


class AnswerEvaluation(BaseModel):
    score: int = Field(ge=0, le=10, description="Score out of 10 for this single answer.")
    feedback: str = Field(description="Concise, specific feedback (2-4 sentences).")
    ideal_answer: str = Field(description="A concise model answer to this question.")


class FinalInterviewReport(BaseModel):
    overall_score: int = Field(ge=0, le=100, description="Overall interview performance, 0-100.")
    strengths: List[str] = Field(description="3-6 concrete strengths shown across the interview.")
    weak_areas: List[str] = Field(description="3-6 concrete areas that need improvement.")
    feedback: str = Field(description="A short overall narrative summary (3-5 sentences).")


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------
_GROUNDING_RULE = (
    "Base any claim about the candidate's resume, skills, or experience only "
    "on the RESUME CONTEXT provided below. If something isn't present there, "
    "say plainly that the resume doesn't mention it — never guess, assume, "
    "or invent resume details."
)

RESUME_EXPERT_SYSTEM = f"""You are the Resume Expert inside an AI interview-prep assistant.
You answer the candidate's questions about their own resume — its ATS
compatibility, skills, projects, strengths, weaknesses, and skill gaps for
roles they're targeting.
{_GROUNDING_RULE}
Keep answers natural and conversational, like a knowledgeable colleague —
not a robotic bullet-point report, unless a list genuinely fits what was asked."""

CAREER_COACH_SYSTEM = f"""You are a Career Coach inside an AI interview-prep assistant, speaking like
a supportive, experienced mentor — not a generic chatbot.
Give practical, specific career and learning guidance grounded in the
candidate's actual resume, skills, and skill gaps. When a target role is
given, tailor your advice toward closing the gap between their current
resume and that role.
{_GROUNDING_RULE}
Be warm and encouraging but honest — real guidance, not empty motivation."""

TUTOR_SYSTEM = """You are an AI Tutor inside an interview-prep assistant.
Explain technical and theory concepts simply and clearly, using short
examples or analogies where they genuinely help. When asked, give theory
practice questions (never coding/code-execution tasks) and fairly evaluate
the candidate's answers with concise, specific feedback.
Keep your tone encouraging and conversational, not repetitive or robotic."""

INTERVIEW_CHAT_SYSTEM = """You are debriefing a candidate one-on-one, right after a completed mock
interview. You have the full record below: the role they interviewed for,
every question asked, their actual answers, the score and feedback already
given for each, and the ideal answer for each.

Use this record to help them improve: discuss their weaknesses in more
depth, suggest better ways to phrase or structure a specific answer they
gave, explain any concept they got wrong, and — if they ask — give them
extra theory practice questions related to this interview and fairly
evaluate their answers to those conversationally, the same way the
interview did. Never invent facts about their performance that aren't in
the record below.
Keep the tone natural, warm, and conversational — like a mentor debriefing
them right after the interview, not a robotic report."""

INTERVIEWER_QUESTIONS_PROMPT = """Generate 10-15 personalized interview questions for a candidate
applying to the role of "{role}".

Strict rules:
- Theory-only questions. Never include coding challenges, "write a function
  that...", debugging exercises, or any request to produce or execute code.
- Questions should probe conceptual understanding, best practices, system
  design reasoning, trade-offs, and relevant experience/behavioral topics.
- Personalize using the candidate's actual resume content below where it's
  relevant — reference their real projects/skills instead of only generic
  questions — but every question must still make sense for the role even
  if the resume context is thin.

RESUME CONTEXT:
{resume_context}
"""

INTERVIEWER_EVALUATION_PROMPT = """The candidate is interviewing for the role of "{role}".

Question asked:
{question}

Candidate's answer:
{answer}

Evaluate this single answer: give a score out of 10, concise specific
feedback (what was good, what was missing or wrong), and a concise ideal
answer. Be fair — reward correct understanding even if the phrasing is
informal — but don't inflate the score for vague or incorrect answers.
"""

INTERVIEWER_REPORT_PROMPT = """The candidate completed a mock theory interview for the role of "{role}".
Here is the full question-by-question record, including the score already
given to each answer:

{qa_summary}

Write a final report: an overall score out of 100 (not simply the average
of the per-question scores — weigh how they did on the harder/more
important questions too), 3-6 concrete strengths shown across the
interview, 3-6 concrete weak areas, and a short overall narrative summary.
"""


# ---------------------------------------------------------------------------
# The service
# ---------------------------------------------------------------------------
class AIAssistantService:
    """One AI-backed service, four modes. All calls to the AI service funnel
    through _chat / the interview methods below."""

    @staticmethod
    def _chat(system_instruction: str, history: list, user_message: str) -> str:
        """Free-form reply for the three conversational modes. `history` is
        prior turns only (not including `user_message`), as
        [{"role": "user"|"assistant", "content": str}, ...]."""
        turns = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in history[-MAX_HISTORY_MESSAGES:]
        ]
        try:
            data = ai_service_post(
                "/chat",
                {"system_instruction": system_instruction, "history": turns, "message": user_message},
            )
        except AIServiceHTTPError as exc:
            raise AIServiceError(f"AI service chat request failed: {exc}") from exc

        reply = data.get("reply")
        if not reply:
            raise AIServiceError("AI service returned an empty reply.")
        return reply

    # -- Shared grounding -----------------------------------------------
    def _resume_context(self, user, query: str, top_k: int = 5) -> str:
        """Combines Module 3's stored analysis (ATS score, strengths,
        weaknesses, skills, skill gaps — none of which live in the raw
        resume text, so RAG alone can't answer questions about them) with
        Module 4's RAG-retrieved raw resume excerpts relevant to `query`."""
        resume = Resume.objects.filter(user=user).first()
        if not resume or resume.status != Resume.STATUS_PROCESSED:
            return "The candidate has not uploaded a resume yet."

        parts = []
        analysis = ResumeAnalysis.objects.filter(resume=resume, status=ResumeAnalysis.STATUS_COMPLETED).first()
        if analysis:
            roles_summary = "; ".join(
                f"{r['role']} (missing: {', '.join(r['missing_skills']) or 'none'})"
                for r in analysis.suggested_roles
            )
            parts.append(
                "RESUME ANALYSIS SUMMARY:\n"
                f"- ATS compatibility score (estimate): {analysis.ats_score}/100\n"
                f"- Strengths: {', '.join(analysis.strengths) or 'none recorded'}\n"
                f"- Weaknesses: {', '.join(analysis.weaknesses) or 'none recorded'}\n"
                f"- Extracted skills: {', '.join(analysis.extracted_skills) or 'none recorded'}\n"
                f"- Suggested roles and missing skills: {roles_summary or 'none recorded'}\n"
                f"- Improvement suggestions: {', '.join(analysis.improvement_suggestions) or 'none recorded'}"
            )

        try:
            chunks = retrieve_relevant_chunks(user, query, top_k=top_k)
        except RAGError:
            chunks = []
        if chunks:
            parts.append("RELEVANT RESUME EXCERPTS:\n" + "\n---\n".join(chunks))

        return "\n\n".join(parts) if parts else "No resume analysis or content is available yet."

    # -- 1. Resume Expert --------------------------------------------------
    def resume_expert_reply(self, user, history: list, message: str) -> str:
        context = self._resume_context(user, message)
        grounded_message = f"RESUME CONTEXT:\n{context}\n\nCANDIDATE QUESTION:\n{message}"
        return self._chat(RESUME_EXPERT_SYSTEM, history, grounded_message)

    # -- 2. AI Interviewer ---------------------------------------------------
    def generate_interview_questions(self, user, role: str) -> List[str]:
        context = self._resume_context(user, f"skills, projects, and experience relevant to {role}", top_k=8)
        prompt = INTERVIEWER_QUESTIONS_PROMPT.format(role=role, resume_context=context)
        try:
            data = ai_service_post("/interview/questions", {"prompt": prompt})
        except AIServiceHTTPError as exc:
            raise AIServiceError(f"AI service request failed: {exc}") from exc
        try:
            result = GeneratedQuestions(**data)
        except ValidationError as exc:
            raise AIServiceError(f"AI service returned an unexpected response: {exc}") from exc
        return result.questions

    def evaluate_interview_answer(self, role: str, question: str, answer: str) -> AnswerEvaluation:
        prompt = INTERVIEWER_EVALUATION_PROMPT.format(role=role, question=question, answer=answer)
        try:
            data = ai_service_post("/interview/evaluate", {"prompt": prompt})
        except AIServiceHTTPError as exc:
            raise AIServiceError(f"AI service request failed: {exc}") from exc
        try:
            return AnswerEvaluation(**data)
        except ValidationError as exc:
            raise AIServiceError(f"AI service returned an unexpected response: {exc}") from exc

    def generate_interview_report(self, role: str, qa_log: List[dict]) -> FinalInterviewReport:
        qa_summary = "\n\n".join(
            f"Q{i+1}: {qa['question']}\nAnswer: {qa['answer']}\nScore given: {qa['score']}/10"
            for i, qa in enumerate(qa_log)
        )
        prompt = INTERVIEWER_REPORT_PROMPT.format(role=role, qa_summary=qa_summary)
        try:
            data = ai_service_post("/interview/report", {"prompt": prompt})
        except AIServiceHTTPError as exc:
            raise AIServiceError(f"AI service request failed: {exc}") from exc
        try:
            return FinalInterviewReport(**data)
        except ValidationError as exc:
            raise AIServiceError(f"AI service returned an unexpected response: {exc}") from exc

    # -- 3. Career Coach -----------------------------------------------------
    def career_coach_reply(self, user, history: list, message: str, role: str = "") -> str:
        query = f"{message} (target role: {role})" if role else message
        context = self._resume_context(user, query)
        role_line = f"Target role the candidate is working toward: {role}\n\n" if role else ""
        grounded_message = f"{role_line}RESUME CONTEXT:\n{context}\n\nCANDIDATE MESSAGE:\n{message}"
        return self._chat(CAREER_COACH_SYSTEM, history, grounded_message)

    # -- 4. AI Tutor -----------------------------------------------------------
    def tutor_reply(self, user, history: list, message: str) -> str:
        return self._chat(TUTOR_SYSTEM, history, message)

    # -- Post-interview review chat (Module 7) --------------------------------
    @staticmethod
    def _interview_context(interview) -> str:
        """Builds the grounding context from one InterviewSession's own
        stored record — role, every question/answer/score/feedback/ideal
        answer, and the final report. No resume/RAG lookup here: the
        interview's own record is the complete, self-contained context this
        mode needs, per spec."""
        qa_lines = [
            f"Q{i}: {qa['question']}\n"
            f"Candidate's answer: {qa['answer']}\n"
            f"Score given: {qa['score']}/10\n"
            f"Feedback given: {qa['feedback']}\n"
            f"Ideal answer: {qa['ideal_answer']}"
            for i, qa in enumerate(interview.qa_log, start=1)
        ]
        report = interview.final_report or {}
        report_summary = (
            f"Overall score: {report.get('overall_score', 'n/a')}/100\n"
            f"Strengths: {', '.join(report.get('strengths', [])) or 'none recorded'}\n"
            f"Weak areas: {', '.join(report.get('weak_areas', [])) or 'none recorded'}\n"
            f"Summary feedback: {report.get('feedback', '')}"
        )
        return (
            f"Role interviewed for: {interview.role}\n\n"
            f"FINAL REPORT:\n{report_summary}\n\n"
            f"QUESTION-BY-QUESTION RECORD:\n" + "\n\n".join(qa_lines)
        )

    def interview_chat_reply(self, interview, history: list, message: str) -> str:
        """`interview` is a completed InterviewSession (Module 5/6). Used by
        Module 7's post-interview chat — a free-form conversation grounded
        entirely in that one interview's own record, not a new interview or
        a new InterviewSession row, even when the user asks for extra
        practice questions."""
        context = self._interview_context(interview)
        grounded_message = f"INTERVIEW CONTEXT:\n{context}\n\nUSER MESSAGE:\n{message}"
        return self._chat(INTERVIEW_CHAT_SYSTEM, history, grounded_message)


ai_assistant = AIAssistantService()
