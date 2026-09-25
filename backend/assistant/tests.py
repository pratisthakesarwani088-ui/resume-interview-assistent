from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.test import TestCase, override_settings, skipUnlessDBFeature
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from assistant.models import ChatMessage, ChatSession, InterviewSession
from assistant.services import AIServiceError, AnswerEvaluation, FinalInterviewReport
from resumes.models import Resume

User = get_user_model()


def _processed_resume(user, text="Backend developer with Python and Django experience."):
    return Resume.objects.create(
        user=user,
        file=ContentFile(b"%PDF-1.4 fake", name="resume.pdf"),
        original_filename="resume.pdf",
        file_size=13,
        extracted_text=text,
        page_count=1,
        status=Resume.STATUS_PROCESSED,
    )


class ChatViewTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="cand@example.com", name="Candidate", password="StrongPass123")
        res = self.client.post(reverse("login"), {"email": "cand@example.com", "password": "StrongPass123"})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")

    def test_get_requires_auth(self):
        self.client.credentials()
        res = self.client.get(reverse("chat_resume_expert"))
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_empty_history_before_any_message(self):
        res = self.client.get(reverse("chat_resume_expert"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["messages"], [])

    def test_post_empty_message_rejected(self):
        res = self.client.post(reverse("chat_resume_expert"), {"message": "   "})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("assistant.views.ai_assistant.resume_expert_reply", return_value="Your resume mentions Python and Django.")
    def test_post_stores_both_turns_and_returns_reply(self, mock_reply):
        res = self.client.post(reverse("chat_resume_expert"), {"message": "What languages do I know?"})
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["role"], "assistant")
        self.assertIn("Python", res.data["content"])

        session = ChatSession.objects.get(user=self.user, mode=ChatSession.MODE_RESUME_EXPERT)
        messages = list(session.messages.order_by("created_at"))
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].role, ChatMessage.ROLE_USER)
        self.assertEqual(messages[1].role, ChatMessage.ROLE_ASSISTANT)

    @patch("assistant.views.ai_assistant.resume_expert_reply", side_effect=AIServiceError("boom"))
    def test_gemini_failure_returns_502_and_does_not_store_partial_turn(self, mock_reply):
        res = self.client.post(reverse("chat_resume_expert"), {"message": "hello"})
        self.assertEqual(res.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertFalse(ChatMessage.objects.filter(session__user=self.user).exists())

    @patch("assistant.views.ai_assistant.career_coach_reply", return_value="Focus on closing your Docker gap.")
    def test_career_coach_stores_selected_role_on_session(self, mock_reply):
        res = self.client.post(
            reverse("chat_career_coach"), {"message": "How do I get this job?", "role": "Backend Developer"}
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        session = ChatSession.objects.get(user=self.user, mode=ChatSession.MODE_CAREER_COACH)
        self.assertEqual(session.selected_role, "Backend Developer")
        mock_reply.assert_called_once()
        self.assertEqual(mock_reply.call_args.kwargs.get("role"), "Backend Developer")

    @patch("assistant.views.ai_assistant.tutor_reply", return_value="A closure is a function bundled with its scope.")
    def test_tutor_mode_independent_of_other_modes(self, mock_reply):
        self.client.post(reverse("chat_tutor"), {"message": "What is a closure?"})
        self.assertTrue(ChatSession.objects.filter(user=self.user, mode=ChatSession.MODE_TUTOR).exists())
        self.assertFalse(ChatSession.objects.filter(user=self.user, mode=ChatSession.MODE_RESUME_EXPERT).exists())


class ChatIsolationTests(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(email="a@example.com", name="A", password="StrongPass123")
        self.user_b = User.objects.create_user(email="b@example.com", name="B", password="StrongPass123")

    def _login(self, email, password):
        res = self.client.post(reverse("login"), {"email": email, "password": password})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")

    @patch("assistant.views.ai_assistant.resume_expert_reply", return_value="reply")
    def test_users_never_see_each_others_messages(self, mock_reply):
        self._login("a@example.com", "StrongPass123")
        self.client.post(reverse("chat_resume_expert"), {"message": "A's question"})

        self._login("b@example.com", "StrongPass123")
        res = self.client.get(reverse("chat_resume_expert"))
        self.assertEqual(res.data["messages"], [])


class InterviewFlowTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="cand@example.com", name="Candidate", password="StrongPass123")
        res = self.client.post(reverse("login"), {"email": "cand@example.com", "password": "StrongPass123"})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")

    def test_start_requires_role(self):
        res = self.client.post(reverse("interview_start"), {})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_start_requires_processed_resume(self):
        res = self.client.post(reverse("interview_start"), {"role": "Backend Developer"})
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)

    @patch("assistant.views.ai_assistant.generate_interview_questions")
    def test_start_creates_interview_with_generated_questions(self, mock_generate):
        mock_generate.return_value = [f"Question {i}?" for i in range(12)]
        _processed_resume(self.user)

        res = self.client.post(reverse("interview_start"), {"role": "Backend Developer"})
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["status"], "in_progress")
        self.assertEqual(res.data["total_questions"], 12)
        self.assertEqual(res.data["current_question"], "Question 0?")

    @patch("assistant.views.ai_assistant.generate_interview_questions")
    def test_start_is_idempotent_while_in_progress(self, mock_generate):
        mock_generate.return_value = [f"Question {i}?" for i in range(10)]
        _processed_resume(self.user)

        first = self.client.post(reverse("interview_start"), {"role": "Backend Developer"})
        second = self.client.post(reverse("interview_start"), {"role": "Frontend Developer"})

        self.assertEqual(first.data["id"], second.data["id"])
        self.assertEqual(second.data["role"], "Backend Developer")  # unchanged — second call was a no-op
        mock_generate.assert_called_once()

    def test_answer_without_active_interview_returns_404(self):
        res = self.client.post(reverse("interview_answer"), {"answer": "Some answer"})
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    @patch("assistant.views.ai_assistant.generate_interview_report")
    @patch("assistant.views.ai_assistant.evaluate_interview_answer")
    @patch("assistant.views.ai_assistant.generate_interview_questions")
    def test_full_interview_flow_to_completion_and_report(self, mock_generate, mock_evaluate, mock_report):
        mock_generate.return_value = ["Q1?", "Q2?"]
        mock_evaluate.return_value = AnswerEvaluation(score=8, feedback="Good answer.", ideal_answer="Ideal answer.")
        mock_report.return_value = FinalInterviewReport(
            overall_score=80, strengths=["Clear communication"], weak_areas=["Depth on scaling"], feedback="Solid overall."
        )
        _processed_resume(self.user)
        self.client.post(reverse("interview_start"), {"role": "Backend Developer"})

        first = self.client.post(reverse("interview_answer"), {"answer": "My answer to Q1"})
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["status"], "in_progress")
        self.assertEqual(first.data["current_question"], "Q2?")
        self.assertEqual(len(first.data["qa_log"]), 1)

        second = self.client.post(reverse("interview_answer"), {"answer": "My answer to Q2"})
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(second.data["status"], "completed")
        self.assertIsNone(second.data["current_question"])
        self.assertEqual(second.data["final_report"]["overall_score"], 80)

        status_res = self.client.get(reverse("interview_status"))
        self.assertTrue(status_res.data["has_interview"])
        self.assertEqual(status_res.data["status"], "completed")

    @patch("assistant.views.ai_assistant.evaluate_interview_answer", side_effect=AIServiceError("boom"))
    @patch("assistant.views.ai_assistant.generate_interview_questions")
    def test_evaluation_failure_returns_502_without_advancing(self, mock_generate, mock_evaluate):
        mock_generate.return_value = ["Q1?", "Q2?"]
        _processed_resume(self.user)
        self.client.post(reverse("interview_start"), {"role": "Backend Developer"})

        res = self.client.post(reverse("interview_answer"), {"answer": "An answer"})
        self.assertEqual(res.status_code, status.HTTP_502_BAD_GATEWAY)
        interview = InterviewSession.objects.get(user=self.user)
        self.assertEqual(interview.current_question_index, 0)
        self.assertEqual(interview.qa_log, [])

    def test_status_with_no_interview(self):
        res = self.client.get(reverse("interview_status"))
        self.assertEqual(res.data, {"has_interview": False})


class InterviewIsolationTests(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(email="a@example.com", name="A", password="StrongPass123")
        self.user_b = User.objects.create_user(email="b@example.com", name="B", password="StrongPass123")

    def _login(self, email, password):
        res = self.client.post(reverse("login"), {"email": email, "password": password})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")

    @patch("assistant.views.ai_assistant.generate_interview_questions")
    def test_users_have_independent_interviews(self, mock_generate):
        mock_generate.return_value = [f"Q{i}?" for i in range(10)]
        _processed_resume(self.user_a)

        self._login("a@example.com", "StrongPass123")
        self.client.post(reverse("interview_start"), {"role": "Backend Developer"})

        self._login("b@example.com", "StrongPass123")
        res = self.client.get(reverse("interview_status"))
        self.assertEqual(res.data, {"has_interview": False})


class OneActiveInterviewConstraintTests(TestCase):
    @skipUnlessDBFeature("supports_partial_indexes")
    def test_db_rejects_a_second_in_progress_interview_for_same_user(self):
        user = User.objects.create_user(email="cand@example.com", name="Candidate", password="StrongPass123")
        InterviewSession.objects.create(user=user, role="Backend Developer", questions=["Q1?"])
        with self.assertRaises(IntegrityError):
            InterviewSession.objects.create(user=user, role="Frontend Developer", questions=["Q1?"])


class InterviewChatReplyServiceTests(TestCase):
    """Module 7: the interview_chat_reply grounding helper. This exercises
    assistant/services.py directly (no HTTP layer) — Gemini itself is
    mocked via the same underlying _chat() Module 5's other modes already use."""

    def test_interview_chat_reply_grounds_in_role_qa_log_and_report(self):
        from assistant.services import INTERVIEW_CHAT_SYSTEM, ai_assistant

        interview = InterviewSession(
            role="Backend Developer",
            qa_log=[
                {
                    "question": "What is REST?",
                    "answer": "An API architectural style",
                    "score": 7,
                    "feedback": "Decent, could be more specific.",
                    "ideal_answer": "REST is an architectural style for networked APIs using stateless requests...",
                }
            ],
            final_report={
                "overall_score": 70,
                "strengths": ["Clear communication"],
                "weak_areas": ["Depth on scaling"],
                "feedback": "Good foundation, needs more depth.",
            },
        )
        with patch.object(ai_assistant, "_chat", return_value="Let's dig into scaling more.") as mock_chat:
            reply = ai_assistant.interview_chat_reply(interview, [], "What should I improve?")

        self.assertEqual(reply, "Let's dig into scaling more.")
        mock_chat.assert_called_once()
        system, history, grounded_message = mock_chat.call_args[0]
        self.assertEqual(system, INTERVIEW_CHAT_SYSTEM)
        self.assertEqual(history, [])
        self.assertIn("Backend Developer", grounded_message)
        self.assertIn("What is REST?", grounded_message)
        self.assertIn("Depth on scaling", grounded_message)
        self.assertIn("What should I improve?", grounded_message)
