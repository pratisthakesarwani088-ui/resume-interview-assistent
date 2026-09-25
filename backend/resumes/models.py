import uuid

from django.conf import settings
from django.db import models


def resume_upload_path(instance, filename):
    """
    Store under media/resumes/user_<id>/<uuid>.pdf — a random stored name so
    the original filename (which a user doesn't control from other users'
    perspective) is never used as a path component, and one user's files
    can't be guessed/listed from another user's.
    """
    return f"resumes/user_{instance.user_id}/{uuid.uuid4().hex}.pdf"


class Resume(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PROCESSED = "processed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSED, "Processed"),
        (STATUS_FAILED, "Failed"),
    ]

    # OneToOne: exactly one resume per user, matching "no replace" + "one PDF" spec.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="resume"
    )
    file = models.FileField(upload_to=resume_upload_path)
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(help_text="Size in bytes")

    extracted_text = models.TextField(blank=True)
    page_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.user.email} — {self.original_filename}"
