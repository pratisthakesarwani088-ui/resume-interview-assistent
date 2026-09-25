from django.urls import path

from .views import ResumeStatusView, ResumeUploadView

urlpatterns = [
    path("upload/", ResumeUploadView.as_view(), name="resume_upload"),
    path("me/", ResumeStatusView.as_view(), name="resume_status"),
]
