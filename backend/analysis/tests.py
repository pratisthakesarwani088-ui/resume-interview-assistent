from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from analysis.models import ResumeAnalysis
from analysis.services import AnalysisError, ResumeAnalysisResult, SuggestedRole
from resumes.models import Resume

User = get_user_model()


def make_fake_result():
    return ResumeAnalysisResult(
        ats_score=72,
        strengths=["Clear project descriptions", "Quantified impact"],
        weaknesses=["No summary section"],
        extracted_skills=["Python", "Django", "PostgreSQL"],
        projects_experience=["Built a REST API for a CRM"],
        suggested_roles=[
            SuggestedRole(
                role="Backend Developer",
                required_skills=["Python", "Django", "SQL", "REST APIs"],
                missing_skills=["Docker"],
            )
        ],
        improvement_suggestions=["Add a professional summary at the top."],
    )


class AnalysisTestsBase(APITestCase):
    def _create_processed_resume(self, user, text="Experienced backend developer with Python and Django."):
        return Resume.objects.create(
            user=user,
            file=ContentFile(b"%PDF-1.4 fake content", name="resume.pdf"),
            original_filename="resume.pdf",
            file_size=20,
            extracted_text=text,
            page_count=1,
            status=Resume.STATUS_PROCESSED,
        )

    def _login(self, email, password):
        res = self.client.post(reverse("login"), {"email": email, "password": password})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")


class AnalyzeResumeViewTests(AnalysisTestsBase):
    def setUp(self):
        self.user = User.objects.create_user(email="cand@example.com", name="Candidate", password="StrongPass123")

    def test_analyze_requires_auth(self):
        res = self.client.post(reverse("analyze_resume"))
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_analyze_requires_resume(self):
        self._login("cand@example.com", "StrongPass123")
        res = self.client.post(reverse("analyze_resume"))
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_analyze_requires_processed_resume(self):
        self._login("cand@example.com", "StrongPass123")
        Resume.objects.create(
            user=self.user,
            file=ContentFile(b"%PDF-1.4", name="resume.pdf"),
            original_filename="resume.pdf",
            file_size=8,
            status=Resume.STATUS_PENDING,
        )
        res = self.client.post(reverse("analyze_resume"))
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)

    @patch("analysis.views.analyze_resume_text")
    def test_analyze_success_stores_structured_result(self, mock_analyze):
        mock_analyze.return_value = make_fake_result()
        self._login("cand@example.com", "StrongPass123")
        self._create_processed_resume(self.user)

        res = self.client.post(reverse("analyze_resume"))
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["status"], "completed")
        self.assertEqual(res.data["ats_score"], 72)
        self.assertEqual(res.data["extracted_skills"], ["Python", "Django", "PostgreSQL"])
        self.assertEqual(res.data["suggested_roles"][0]["role"], "Backend Developer")
        self.assertEqual(res.data["suggested_roles"][0]["missing_skills"], ["Docker"])
        mock_analyze.assert_called_once()

    @patch("analysis.views.analyze_resume_text")
    def test_analyze_is_idempotent_once_completed(self, mock_analyze):
        mock_analyze.return_value = make_fake_result()
        self._login("cand@example.com", "StrongPass123")
        self._create_processed_resume(self.user)

        first = self.client.post(reverse("analyze_resume"))
        second = self.client.post(reverse("analyze_resume"))

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        mock_analyze.assert_called_once()  # second call reused the stored result

    @patch("analysis.views.analyze_resume_text")
    def test_analyze_handles_gemini_failure_gracefully(self, mock_analyze):
        mock_analyze.side_effect = AnalysisError("Gemini request failed: timeout")
        self._login("cand@example.com", "StrongPass123")
        self._create_processed_resume(self.user)

        res = self.client.post(reverse("analyze_resume"))
        self.assertEqual(res.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertTrue(ResumeAnalysis.objects.filter(resume__user=self.user, status="failed").exists())


class AnalysisStatusViewTests(AnalysisTestsBase):
    def setUp(self):
        self.user_a = User.objects.create_user(email="a@example.com", name="User A", password="StrongPass123")
        self.user_b = User.objects.create_user(email="b@example.com", name="User B", password="StrongPass123")

    def test_status_requires_auth(self):
        res = self.client.get(reverse("analysis_status"))
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_status_no_resume(self):
        self._login("a@example.com", "StrongPass123")
        res = self.client.get(reverse("analysis_status"))
        self.assertEqual(res.data, {"has_resume": False, "has_analysis": False})

    def test_status_resume_without_analysis(self):
        self._login("a@example.com", "StrongPass123")
        self._create_processed_resume(self.user_a)
        res = self.client.get(reverse("analysis_status"))
        self.assertEqual(res.data, {"has_resume": True, "has_analysis": False})

    @patch("analysis.views.analyze_resume_text")
    def test_status_reflects_own_analysis_only(self, mock_analyze):
        mock_analyze.return_value = make_fake_result()
        self._login("a@example.com", "StrongPass123")
        self._create_processed_resume(self.user_a)
        self.client.post(reverse("analyze_resume"))

        res_a = self.client.get(reverse("analysis_status"))
        self.assertTrue(res_a.data["has_analysis"])
        self.assertEqual(res_a.data["analysis"]["ats_score"], 72)

        # User B has no resume/analysis of their own — never sees A's data.
        self._login("b@example.com", "StrongPass123")
        res_b = self.client.get(reverse("analysis_status"))
        self.assertEqual(res_b.data, {"has_resume": False, "has_analysis": False})
