from django.urls import path

from .models import ChatSession
from .views import ChatView, InterviewAnswerView, InterviewStartView, InterviewStatusView

urlpatterns = [
    path("chat/resume-expert/", ChatView.as_view(mode=ChatSession.MODE_RESUME_EXPERT), name="chat_resume_expert"),
    path("chat/career-coach/", ChatView.as_view(mode=ChatSession.MODE_CAREER_COACH), name="chat_career_coach"),
    path("chat/tutor/", ChatView.as_view(mode=ChatSession.MODE_TUTOR), name="chat_tutor"),
    path("interview/status/", InterviewStatusView.as_view(), name="interview_status"),
    path("interview/start/", InterviewStartView.as_view(), name="interview_start"),
    path("interview/answer/", InterviewAnswerView.as_view(), name="interview_answer"),
]
