from django.db import transaction
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from assistant.services import AIServiceError, ai_assistant

from .models import InterviewChatMessage
from .serializers import InterviewChatMessageSerializer
from .views import _own_completed_qs

MAX_HISTORY_FOR_PROMPT = 20


class InterviewChatView(APIView):
    """
    GET  /api/history/interviews/<id>/chat/  — this interview's chat history
    POST /api/history/interviews/<id>/chat/  — send a message, get the reply

    Reuses history/views.py's `_own_completed_qs`, so the ownership rule is
    identical to every other history endpoint: the interview must belong to
    request.user and be completed, or this 404s exactly like it doesn't
    exist. No new interview or InterviewSession is ever created here, even
    when the reply includes extra practice questions — this is chat only.
    """

    permission_classes = [permissions.IsAuthenticated]

    def _get_interview(self, request, interview_id):
        return _own_completed_qs(request.user).filter(id=interview_id).first()

    def get(self, request, interview_id):
        interview = self._get_interview(request, interview_id)
        if not interview:
            return Response({"detail": "Interview not found."}, status=status.HTTP_404_NOT_FOUND)
        messages = interview.chat_messages.all()
        return Response(InterviewChatMessageSerializer(messages, many=True).data)

    def post(self, request, interview_id):
        interview = self._get_interview(request, interview_id)
        if not interview:
            return Response({"detail": "Interview not found."}, status=status.HTTP_404_NOT_FOUND)

        text = (request.data.get("message") or "").strip()
        if not text:
            return Response({"detail": "Message cannot be empty."}, status=status.HTTP_400_BAD_REQUEST)

        history = list(
            interview.chat_messages.order_by("created_at").values("role", "content")
        )[-MAX_HISTORY_FOR_PROMPT:]

        try:
            reply = ai_assistant.interview_chat_reply(interview, history, text)
        except AIServiceError:
            return Response(
                {"detail": "The assistant is unavailable right now. Please try again."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        with transaction.atomic():
            InterviewChatMessage.objects.create(
                interview=interview, role=InterviewChatMessage.ROLE_USER, content=text
            )
            assistant_message = InterviewChatMessage.objects.create(
                interview=interview, role=InterviewChatMessage.ROLE_ASSISTANT, content=reply
            )

        return Response(InterviewChatMessageSerializer(assistant_message).data, status=status.HTTP_201_CREATED)
