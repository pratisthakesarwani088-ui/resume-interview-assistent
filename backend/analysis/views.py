from django.db import transaction
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from resumes.models import Resume

from .models import ResumeAnalysis
from .serializers import ResumeAnalysisSerializer
from .services import AnalysisError, analyze_resume_text


def _get_own_resume(user):
    """Returns request.user's resume, or None. Never accepts/looks up an ID —
    this is the only way this module reads a resume, so cross-user access
    to someone else's resume/analysis is structurally impossible."""
    return Resume.objects.filter(user=user).first()


class AnalyzeResumeView(APIView):
    """
    POST /api/analysis/analyze/

    Runs (or returns the existing) Gemini analysis for request.user's own
    resume. Idempotent on success: a second call while a completed analysis
    already exists just returns it, rather than re-spending an API call.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        resume = _get_own_resume(request.user)
        if not resume:
            return Response(
                {"detail": "Upload a resume before requesting an analysis."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if resume.status != Resume.STATUS_PROCESSED:
            return Response(
                {"detail": "Your resume is still being processed. Try again shortly."},
                status=status.HTTP_409_CONFLICT,
            )

        existing = ResumeAnalysis.objects.filter(resume=resume).first()
        if existing and existing.status == ResumeAnalysis.STATUS_COMPLETED:
            return Response(ResumeAnalysisSerializer(existing).data, status=status.HTTP_200_OK)

        try:
            result = analyze_resume_text(resume.extracted_text)
        except AnalysisError:
            with transaction.atomic():
                analysis, _ = ResumeAnalysis.objects.update_or_create(
                    resume=resume,
                    defaults={"status": ResumeAnalysis.STATUS_FAILED},
                )
            return Response(
                {"detail": "Resume analysis failed. Please try again in a moment."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        with transaction.atomic():
            analysis, _ = ResumeAnalysis.objects.update_or_create(
                resume=resume,
                defaults={
                    "status": ResumeAnalysis.STATUS_COMPLETED,
                    "ats_score": result.ats_score,
                    "strengths": result.strengths,
                    "weaknesses": result.weaknesses,
                    "extracted_skills": result.extracted_skills,
                    "projects_experience": result.projects_experience,
                    "suggested_roles": [role.model_dump() for role in result.suggested_roles],
                    "improvement_suggestions": result.improvement_suggestions,
                },
            )

        was_created = analysis.created_at == analysis.updated_at
        return Response(
            ResumeAnalysisSerializer(analysis).data,
            status=status.HTTP_201_CREATED if was_created else status.HTTP_200_OK,
        )


class AnalysisStatusView(APIView):
    """
    GET /api/analysis/me/  -> always scoped to request.user; never a pk lookup.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        resume = _get_own_resume(request.user)
        if not resume:
            return Response({"has_resume": False, "has_analysis": False})

        analysis = ResumeAnalysis.objects.filter(resume=resume).first()
        if not analysis:
            return Response({"has_resume": True, "has_analysis": False})

        return Response(
            {
                "has_resume": True,
                "has_analysis": True,
                "analysis": ResumeAnalysisSerializer(analysis).data,
            }
        )
