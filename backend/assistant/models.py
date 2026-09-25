from django.conf import settings
from django.db import models
from django.db.models import Q


class ChatSession(models.Model):
    """One ongoing conversation per (user, mode) — not a list of named
    chats. This keeps 'maintain conversation context' simple: there's
    exactly one thread to look up and continue for each mode."""

    MODE_RESUME_EXPERT = "resume_expert"
    MODE_CAREER_COACH = "career_coach"
    MODE_TUTOR = "tutor"
    MODE_CHOICES = [
        (MODE_RESUME_EXPERT, "Resume Expert"),
        (MODE_CAREER_COACH, "Career Coach"),
        (MODE_TUTOR, "AI Tutor"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_sessions")
    mode = models.CharField(max_length=20, choices=MODE_CHOICES)
    # Optional target role for Career Coach guidance (e.g. one of Module 3's
    # suggested_roles). Blank means "general" advice not tied to one role.
    selected_role = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "mode"], name="one_session_per_user_mode"),
        ]

    def __str__(self):
        return f"{self.user.email} — {self.mode}"


class ChatMessage(models.Model):
    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    ROLE_CHOICES = [(ROLE_USER, "User"), (ROLE_ASSISTANT, "Assistant")]

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role}: {self.content[:40]}"


class InterviewSession(models.Model):
    """One structured mock-interview run for one role. A user can have many
    of these over time (one per role/attempt), but only one may be
    in_progress at once — enforced both here (application check before
    creating) and at the DB level via the partial unique constraint below."""

    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = [
        (STATUS_IN_PROGRESS, "In progress"),
        (STATUS_COMPLETED, "Completed"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="interview_sessions")
    role = models.CharField(max_length=150)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_IN_PROGRESS)
    # Module 6 (Interview History): optional user-set display title. Blank
    # means "not renamed yet" — the history UI falls back to `role` for
    # display, so this stays optional rather than needing a default value
    # computed at save time.
    title = models.CharField(max_length=200, blank=True)

    # Generated once at start; theory-only interview questions for `role`.
    questions = models.JSONField(default=list)
    current_question_index = models.PositiveIntegerField(default=0)
    # Each entry: {"question": str, "answer": str, "score": int, "feedback": str, "ideal_answer": str}
    qa_log = models.JSONField(default=list)
    # {"overall_score": int, "strengths": [str], "weak_areas": [str], "feedback": str}
    final_report = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(status="in_progress"),
                name="one_active_interview_per_user",
            ),
        ]

    def __str__(self):
        return f"{self.user.email} — {self.role} ({self.status})"
