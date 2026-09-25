from django.db import models

from resumes.models import Resume


class ResumeIndex(models.Model):
    STATUS_PENDING = "pending"
    STATUS_INDEXED = "indexed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_INDEXED, "Indexed"),
        (STATUS_FAILED, "Failed"),
    ]

    # One index record per resume — mirrors the one-resume-per-user design
    # from Module 2. This table only tracks indexing *state*; the actual
    # vectors live in ChromaDB, keyed by the same resume_id in their metadata.
    resume = models.OneToOneField(Resume, on_delete=models.CASCADE, related_name="rag_index")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    chunk_count = models.PositiveIntegerField(default=0)

    # SHA-256 of the exact text that was indexed. Resumes can't be replaced
    # (Module 2 has no replace/delete flow), so this should never change in
    # practice — it exists as a cheap, explicit "is this actually stale?"
    # check rather than assuming indexed-once-means-indexed-forever.
    content_hash = models.CharField(max_length=64, blank=True)

    error_message = models.TextField(blank=True)
    indexed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"RAG index for {self.resume.user.email} ({self.status})"
