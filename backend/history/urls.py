from django.urls import path

from .chat_views import InterviewChatView
from .views import InterviewHistoryDetailView, InterviewHistoryListView

urlpatterns = [
    path("interviews/", InterviewHistoryListView.as_view(), name="history_list"),
    path("interviews/<int:interview_id>/", InterviewHistoryDetailView.as_view(), name="history_detail"),
    path("interviews/<int:interview_id>/chat/", InterviewChatView.as_view(), name="interview_chat"),
]
