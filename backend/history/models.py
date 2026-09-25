from django.db import models

from assistant.models import InterviewSession


class InterviewChatMessage(models.Model):
    """Post-interview review chat, one thread per InterviewSession (not per
    user+mode like Module 5's ChatSession — a user can have many completed
    interviews, each with its own review conversation). Deleting the
    InterviewSession (Module 6's delete endpoint) cascades to delete all of
    its chat messages automatically via on_delete=CASCADE below — no extra
    cleanup code needed anywhere."""

    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    ROLE_CHOICES = [(ROLE_USER, "User"), (ROLE_ASSISTANT, "Assistant")]

    interview = models.ForeignKey(InterviewSession, on_delete=models.CASCADE, related_name="chat_messages")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role}: {self.content[:40]}"
