from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from assistant.models import InterviewSession
from assistant.services import AIServiceError

from .models import InterviewChatMessage

User = get_user_model()


class InterviewHistoryListTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="cand@example.com", name="Candidate", password="StrongPass123")
        res = self.client.post(reverse("login"), {"email": "cand@example.com", "password": "StrongPass123"})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")

    def test_requires_auth(self):
        self.client.credentials()
        res = self.client.get(reverse("history_list"))
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_empty_list_when_no_completed_interviews(self):
        res = self.client.get(reverse("history_list"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, [])

    def test_in_progress_interview_excluded_from_history(self):
        InterviewSession.objects.create(
            user=self.user, role="Backend Developer", status=InterviewSession.STATUS_IN_PROGRESS, questions=["Q1?"]
        )
        res = self.client.get(reverse("history_list"))
        self.assertEqual(res.data, [])

    def test_completed_interview_appears_with_expected_fields(self):
        InterviewSession.objects.create(
            user=self.user,
            role="Frontend Developer",
            status=InterviewSession.STATUS_COMPLETED,
            questions=["Q1?", "Q2?"],
            qa_log=[{"question": "Q1?", "answer": "A1", "score": 8, "feedback": "Good", "ideal_answer": "Ideal"}],
            final_report={"overall_score": 80, "strengths": ["x"], "weak_areas": ["y"], "feedback": "z"},
        )
        res = self.client.get(reverse("history_list"))
        self.assertEqual(len(res.data), 1)
        item = res.data[0]
        self.assertEqual(item["role"], "Frontend Developer")
        self.assertEqual(item["title"], "Frontend Developer")  # falls back to role when untitled
        self.assertEqual(item["overall_score"], 80)
        self.assertEqual(item["question_count"], 2)
        self.assertEqual(item["status"], "completed")

    def test_list_ordered_most_recently_completed_first(self):
        older = InterviewSession.objects.create(
            user=self.user, role="A", status=InterviewSession.STATUS_COMPLETED, questions=["Q?"]
        )
        newer = InterviewSession.objects.create(
            user=self.user, role="B", status=InterviewSession.STATUS_COMPLETED, questions=["Q?"]
        )
        res = self.client.get(reverse("history_list"))
        self.assertEqual(res.data[0]["id"], newer.id)
        self.assertEqual(res.data[1]["id"], older.id)


class InterviewHistoryDetailRenameDeleteTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="cand@example.com", name="Candidate", password="StrongPass123")
        res = self.client.post(reverse("login"), {"email": "cand@example.com", "password": "StrongPass123"})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        self.interview = InterviewSession.objects.create(
            user=self.user,
            role="Backend Developer",
            status=InterviewSession.STATUS_COMPLETED,
            questions=["Q1?", "Q2?"],
            qa_log=[
                {"question": "Q1?", "answer": "A1", "score": 7, "feedback": "Decent", "ideal_answer": "Ideal1"},
                {"question": "Q2?", "answer": "A2", "score": 9, "feedback": "Great", "ideal_answer": "Ideal2"},
            ],
            final_report={"overall_score": 82, "strengths": ["Clarity"], "weak_areas": ["Depth"], "feedback": "Solid."},
        )

    def test_detail_returns_full_qa_and_report(self):
        res = self.client.get(reverse("history_detail", args=[self.interview.id]))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["qa_log"]), 2)
        self.assertEqual(res.data["qa_log"][1]["ideal_answer"], "Ideal2")
        self.assertEqual(res.data["final_report"]["overall_score"], 82)
        self.assertEqual(res.data["questions"], ["Q1?", "Q2?"])

    def test_detail_404_for_in_progress_interview(self):
        in_progress = InterviewSession.objects.create(
            user=self.user, role="X", status=InterviewSession.STATUS_IN_PROGRESS, questions=["Q?"]
        )
        res = self.client.get(reverse("history_detail", args=[in_progress.id]))
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_detail_404_for_nonexistent_id(self):
        res = self.client.get(reverse("history_detail", args=[999999]))
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_rename_updates_title_without_changing_completion_date(self):
        original_updated_at = self.interview.updated_at
        res = self.client.patch(reverse("history_detail", args=[self.interview.id]), {"title": "My best attempt"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["title"], "My best attempt")

        self.interview.refresh_from_db()
        self.assertEqual(self.interview.title, "My best attempt")
        self.assertEqual(self.interview.updated_at, original_updated_at)

    def test_rename_rejects_overly_long_title(self):
        res = self.client.patch(reverse("history_detail", args=[self.interview.id]), {"title": "x" * 201})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.interview.refresh_from_db()
        self.assertEqual(self.interview.title, "")

    def test_rename_to_blank_resets_to_role_fallback(self):
        self.interview.title = "Old title"
        self.interview.save(update_fields=["title"])
        res = self.client.patch(reverse("history_detail", args=[self.interview.id]), {"title": ""})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["title"], "Backend Developer")  # blank -> falls back to role

    def test_delete_removes_interview_and_its_data(self):
        res = self.client.delete(reverse("history_detail", args=[self.interview.id]))
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(InterviewSession.objects.filter(id=self.interview.id).exists())

    def test_delete_nonexistent_returns_404(self):
        res = self.client.delete(reverse("history_detail", args=[999999]))
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)


class InterviewHistoryIsolationTests(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(email="a@example.com", name="A", password="StrongPass123")
        self.user_b = User.objects.create_user(email="b@example.com", name="B", password="StrongPass123")
        self.interview_a = InterviewSession.objects.create(
            user=self.user_a,
            role="Backend Developer",
            status=InterviewSession.STATUS_COMPLETED,
            questions=["Q?"],
            final_report={"overall_score": 70, "strengths": [], "weak_areas": [], "feedback": ""},
        )

    def _login(self, email, password):
        res = self.client.post(reverse("login"), {"email": email, "password": password})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")

    def test_user_b_list_excludes_user_a_interview(self):
        self._login("b@example.com", "StrongPass123")
        res = self.client.get(reverse("history_list"))
        self.assertEqual(res.data, [])

    def test_user_b_cannot_view_user_a_detail(self):
        self._login("b@example.com", "StrongPass123")
        res = self.client.get(reverse("history_detail", args=[self.interview_a.id]))
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_b_cannot_rename_user_a_interview(self):
        self._login("b@example.com", "StrongPass123")
        res = self.client.patch(reverse("history_detail", args=[self.interview_a.id]), {"title": "Hijacked"})
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.interview_a.refresh_from_db()
        self.assertEqual(self.interview_a.title, "")

    def test_user_b_cannot_delete_user_a_interview(self):
        self._login("b@example.com", "StrongPass123")
        res = self.client.delete(reverse("history_detail", args=[self.interview_a.id]))
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(InterviewSession.objects.filter(id=self.interview_a.id).exists())


class InterviewChatTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="cand@example.com", name="Candidate", password="StrongPass123")
        res = self.client.post(reverse("login"), {"email": "cand@example.com", "password": "StrongPass123"})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        self.interview = InterviewSession.objects.create(
            user=self.user,
            role="Backend Developer",
            status=InterviewSession.STATUS_COMPLETED,
            questions=["Q1?"],
            qa_log=[{"question": "Q1?", "answer": "A1", "score": 6, "feedback": "OK", "ideal_answer": "Ideal"}],
            final_report={"overall_score": 60, "strengths": [], "weak_areas": ["Depth"], "feedback": "Needs work."},
        )

    def test_get_requires_auth(self):
        self.client.credentials()
        res = self.client.get(reverse("interview_chat", args=[self.interview.id]))
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_empty_history_before_any_message(self):
        res = self.client.get(reverse("interview_chat", args=[self.interview.id]))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, [])

    def test_chat_404_for_in_progress_interview(self):
        in_progress = InterviewSession.objects.create(
            user=self.user, role="X", status=InterviewSession.STATUS_IN_PROGRESS, questions=["Q?"]
        )
        res = self.client.get(reverse("interview_chat", args=[in_progress.id]))
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_chat_404_for_nonexistent_interview(self):
        res = self.client.get(reverse("interview_chat", args=[999999]))
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_post_empty_message_rejected(self):
        res = self.client.post(reverse("interview_chat", args=[self.interview.id]), {"message": "   "})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("history.chat_views.ai_assistant.interview_chat_reply", return_value="Your weak area was depth on scaling.")
    def test_post_stores_both_turns_and_returns_reply(self, mock_reply):
        res = self.client.post(
            reverse("interview_chat", args=[self.interview.id]), {"message": "What was my weakness?"}
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["role"], "assistant")
        self.assertIn("depth", res.data["content"].lower())

        messages = list(InterviewChatMessage.objects.filter(interview=self.interview).order_by("created_at"))
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].role, InterviewChatMessage.ROLE_USER)
        self.assertEqual(messages[1].role, InterviewChatMessage.ROLE_ASSISTANT)
        mock_reply.assert_called_once()

    @patch("history.chat_views.ai_assistant.interview_chat_reply", side_effect=AIServiceError("boom"))
    def test_gemini_failure_returns_502_without_partial_storage(self, mock_reply):
        res = self.client.post(reverse("interview_chat", args=[self.interview.id]), {"message": "hi"})
        self.assertEqual(res.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertFalse(InterviewChatMessage.objects.filter(interview=self.interview).exists())

    def test_deleting_interview_deletes_its_chat_messages(self):
        InterviewChatMessage.objects.create(interview=self.interview, role="user", content="hi")
        InterviewChatMessage.objects.create(interview=self.interview, role="assistant", content="hello")
        self.assertEqual(InterviewChatMessage.objects.filter(interview=self.interview).count(), 2)

        res = self.client.delete(reverse("history_detail", args=[self.interview.id]))
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(InterviewChatMessage.objects.filter(interview_id=self.interview.id).count(), 0)


class InterviewChatIsolationTests(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(email="a@example.com", name="A", password="StrongPass123")
        self.user_b = User.objects.create_user(email="b@example.com", name="B", password="StrongPass123")
        self.interview_a = InterviewSession.objects.create(
            user=self.user_a,
            role="Backend Developer",
            status=InterviewSession.STATUS_COMPLETED,
            questions=["Q?"],
        )

    def _login(self, email, password):
        res = self.client.post(reverse("login"), {"email": email, "password": password})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")

    def test_user_b_cannot_view_user_a_chat_history(self):
        self._login("b@example.com", "StrongPass123")
        res = self.client.get(reverse("interview_chat", args=[self.interview_a.id]))
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    @patch("history.chat_views.ai_assistant.interview_chat_reply", return_value="reply")
    def test_user_b_cannot_post_to_user_a_chat(self, mock_reply):
        self._login("b@example.com", "StrongPass123")
        res = self.client.post(reverse("interview_chat", args=[self.interview_a.id]), {"message": "hi"})
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        mock_reply.assert_not_called()
        self.assertFalse(InterviewChatMessage.objects.filter(interview=self.interview_a).exists())
