from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from assistant.models import InterviewSession

from .serializers import InterviewHistoryDetailSerializer, InterviewHistoryListSerializer

TITLE_MAX_LENGTH = 200


def _own_completed_qs(user):
    """History only ever shows *completed* interviews — an in_progress one
    isn't history yet, it's still visible via Module 5's own
    /api/assistant/interview/status/. Always filtered by user; every view
    below builds on this, so there is no query anywhere in this app that
    could return another user's interview."""
    return InterviewSession.objects.filter(user=user, status=InterviewSession.STATUS_COMPLETED)


class InterviewHistoryListView(generics.ListAPIView):
    """GET /api/history/interviews/ — most recently completed first."""

    serializer_class = InterviewHistoryListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return _own_completed_qs(self.request.user).order_by("-updated_at", "-id")


class InterviewHistoryDetailView(APIView):
    """
    GET    /api/history/interviews/<id>/  — full detail (questions, qa_log, final_report)
    PATCH  /api/history/interviews/<id>/  — rename (body: {"title": "..."})
    DELETE /api/history/interviews/<id>/  — delete the interview and all its data

    `interview_id` is only ever matched against `_own_completed_qs(request.user)`,
    so an interview belonging to another user — or one that isn't completed —
    is indistinguishable from a nonexistent one: always 404, never 403,
    which avoids confirming another user's interview even exists.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, interview_id):
        interview = _own_completed_qs(request.user).filter(id=interview_id).first()
        if not interview:
            return Response({"detail": "Interview not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(InterviewHistoryDetailSerializer(interview).data)

    def patch(self, request, interview_id):
        title = (request.data.get("title") or "").strip()
        if len(title) > TITLE_MAX_LENGTH:
            return Response(
                {"detail": f"Title is too long ({TITLE_MAX_LENGTH} characters max)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # QuerySet.update() — unlike .save() — does not trigger auto_now,
        # so renaming never shifts `updated_at` (and therefore never shifts
        # the "date" shown in history) away from when the interview was
        # actually completed. This is why rename doesn't fetch-then-save.
        updated = _own_completed_qs(request.user).filter(id=interview_id).update(title=title)
        if not updated:
            return Response({"detail": "Interview not found."}, status=status.HTTP_404_NOT_FOUND)

        interview = _own_completed_qs(request.user).get(id=interview_id)
        return Response(InterviewHistoryDetailSerializer(interview).data)

    def delete(self, request, interview_id):
        interview = _own_completed_qs(request.user).filter(id=interview_id).first()
        if not interview:
            return Response({"detail": "Interview not found."}, status=status.HTTP_404_NOT_FOUND)
        # Everything for this interview (questions, qa_log, final_report)
        # lives on this one row — no related tables, so one delete is the
        # whole "and all related interview data" requirement.
        interview.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
