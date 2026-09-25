from django.urls import path

from .views import AnalysisStatusView, AnalyzeResumeView

urlpatterns = [
    path("analyze/", AnalyzeResumeView.as_view(), name="analyze_resume"),
    path("me/", AnalysisStatusView.as_view(), name="analysis_status"),
]
