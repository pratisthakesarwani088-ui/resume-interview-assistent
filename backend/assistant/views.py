from django.db import transaction
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from resumes.models import Resume

from .models import ChatMessage, ChatSession, InterviewSession
from .serializers import ChatMessageSerializer
from .services import AIServiceError, ai_assistant

MAX_HISTORY_FOR_PROMPT = 20


class ChatView(APIView):
    """
    GET/POST /api/assistant/chat/<mode>/

    One view class serves all three conversational modes (resume_expert,
    career_coach, tutor) — `mode` is fixed per URL via as_view(mode=...), so
    there's exactly one code path for "get history" / "send a message"
    regardless of which mode it is. Always resolves to request.user's own
    single session for that mode; no session ID is ever accepted from the
    client, so there is no way to address another user's conversation.
    """

    permission_classes = [permissions.IsAuthenticated]
    mode = None  # set by as_view(mode=ChatSession.MODE_...)

    def get(self, request):
        session = ChatSession.objects.filter(user=request.user, mode=self.mode).first()
        messages = session.messages.all() if session else ChatMessage.objects.none()
        return Response(
            {
                "mode": self.mode,
                "selected_role": session.selected_role if session else "",
                "messages": ChatMessageSerializer(messages, many=True).data,
            }
        )

    def post(self, request):
        text = (request.data.get("message") or "").strip()
        if not text:
            return Response({"detail": "Message cannot be empty."}, status=status.HTTP_400_BAD_REQUEST)

        role = (request.data.get("role") or "").strip()

        session, _ = ChatSession.objects.get_or_create(user=request.user, mode=self.mode)
        if role and role != session.selected_role:
            session.selected_role = role
            session.save(update_fields=["selected_role"])

        history = list(
            session.messages.order_by("created_at").values("role", "content")
        )[-MAX_HISTORY_FOR_PROMPT:]

        try:
            if self.mode == ChatSession.MODE_RESUME_EXPERT:
                reply = ai_assistant.resume_expert_reply(request.user, history, text)
            elif self.mode == ChatSession.MODE_CAREER_COACH:
                reply = ai_assistant.career_coach_reply(request.user, history, text, role=session.selected_role)
            else:
                reply = ai_assistant.tutor_reply(request.user, history, text)
        except AIServiceError:
            return Response(
                {"detail": "The assistant is unavailable right now. Please try again."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        with transaction.atomic():
            ChatMessage.objects.create(session=session, role=ChatMessage.ROLE_USER, content=text)
            assistant_message = ChatMessage.objects.create(
                session=session, role=ChatMessage.ROLE_ASSISTANT, content=reply
            )

        return Response(ChatMessageSerializer(assistant_message).data, status=status.HTTP_201_CREATED)


def _serialize_interview(interview: InterviewSession) -> dict:
    total = len(interview.questions)
    idx = interview.current_question_index
    current_question = (
        interview.questions[idx]
        if interview.status == InterviewSession.STATUS_IN_PROGRESS and idx < total
        else None
    )
    return {
        "id": interview.id,
        "role": interview.role,
        "title": interview.title,
        "status": interview.status,
        "total_questions": total,
        "current_question_index": idx,
        "current_question": current_question,
        "qa_log": interview.qa_log,
        "final_report": interview.final_report,
    }


class InterviewStatusView(APIView):
    """GET /api/assistant/interview/status/ — the in-progress interview if
    there is one, else the most recently completed one, else has_interview:
    false. Always scoped to request.user; no interview ID is ever accepted."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        interview = InterviewSession.objects.filter(
            user=request.user, status=InterviewSession.STATUS_IN_PROGRESS
        ).first()
        if not interview:
            interview = (
                InterviewSession.objects.filter(user=request.user, status=InterviewSession.STATUS_COMPLETED)
                .order_by("-updated_at")
                .first()
            )
        if not interview:
            return Response({"has_interview": False})
        return Response({"has_interview": True, **_serialize_interview(interview)})


class InterviewStartView(APIView):
    """POST /api/assistant/interview/start/  body: {"role": "..."}

    Idempotent while an interview is already in progress: returns the
    existing one rather than starting a second (also enforced at the DB
    level by a partial unique constraint on InterviewSession)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        role = (request.data.get("role") or "").strip()
        if not role:
            return Response({"detail": "A role is required to start an interview."}, status=status.HTTP_400_BAD_REQUEST)

        existing = InterviewSession.objects.filter(
            user=request.user, status=InterviewSession.STATUS_IN_PROGRESS
        ).first()
        if existing:
            return Response(_serialize_interview(existing), status=status.HTTP_200_OK)

        resume = Resume.objects.filter(user=request.user).first()
        if not resume or resume.status != Resume.STATUS_PROCESSED:
            return Response(
                {"detail": "Upload and process your resume before starting an interview."},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            questions = ai_assistant.generate_interview_questions(request.user, role)
        except AIServiceError:
            return Response(
                {"detail": "Couldn't generate interview questions right now. Please try again."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        interview = InterviewSession.objects.create(user=request.user, role=role, questions=questions)
        return Response(_serialize_interview(interview), status=status.HTTP_201_CREATED)


class InterviewAnswerView(APIView):
    """POST /api/assistant/interview/answer/  body: {"answer": "..."}

    Evaluates the answer to request.user's current interview question,
    advances to the next one, and — on the last question — generates the
    final report and marks the interview completed. No interview ID is
    accepted; this always operates on request.user's own in-progress interview."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        answer = (request.data.get("answer") or "").strip()
        if not answer:
            return Response({"detail": "Answer cannot be empty."}, status=status.HTTP_400_BAD_REQUEST)

        interview = InterviewSession.objects.filter(
            user=request.user, status=InterviewSession.STATUS_IN_PROGRESS
        ).first()
        if not interview:
            return Response({"detail": "No interview is currently in progress."}, status=status.HTTP_404_NOT_FOUND)

        idx = interview.current_question_index
        if idx >= len(interview.questions):
            return Response({"detail": "This interview has no more questions."}, status=status.HTTP_409_CONFLICT)

        question = interview.questions[idx]

        try:
            evaluation = ai_assistant.evaluate_interview_answer(interview.role, question, answer)
        except AIServiceError:
            return Response(
                {"detail": "Couldn't evaluate that answer right now. Please try again."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        interview.qa_log.append(
            {
                "question": question,
                "answer": answer,
                "score": evaluation.score,
                "feedback": evaluation.feedback,
                "ideal_answer": evaluation.ideal_answer,
            }
        )
        interview.current_question_index += 1

        update_fields = ["qa_log", "current_question_index", "updated_at"]
        if interview.current_question_index >= len(interview.questions):
            interview.status = InterviewSession.STATUS_COMPLETED
            update_fields.append("status")
            try:
                report = ai_assistant.generate_interview_report(interview.role, interview.qa_log)
                interview.final_report = report.model_dump()
                update_fields.append("final_report")
            except AIServiceError:
                # The interview still completed and every answer's score/
                # feedback is preserved — only the summary report failed to
                # generate. Don't lose the qa_log over that.
                pass

        interview.save(update_fields=update_fields)
        return Response(_serialize_interview(interview), status=status.HTTP_200_OK)
