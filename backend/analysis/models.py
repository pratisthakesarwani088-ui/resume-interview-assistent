from django.db import models

from resumes.models import Resume


class ResumeAnalysis(models.Model):
    STATUS_PENDING = "pending"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    # One analysis per resume (and a resume is already one-per-user), so
    # isolation and "no duplicate analysis" both fall out of the schema.
    resume = models.OneToOneField(Resume, on_delete=models.CASCADE, related_name="analysis")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    # ATS compatibility score, 0-100 — always presented to the user as an
    # estimate, never as a guaranteed/official ATS result.
    ats_score = models.PositiveSmallIntegerField(null=True, blank=True)

    strengths = models.JSONField(default=list, blank=True)
    weaknesses = models.JSONField(default=list, blank=True)
    extracted_skills = models.JSONField(default=list, blank=True)
    projects_experience = models.JSONField(default=list, blank=True)
    # Each item: {"role": str, "required_skills": [str], "missing_skills": [str]}
    suggested_roles = models.JSONField(default=list, blank=True)
    improvement_suggestions = models.JSONField(default=list, blank=True)

    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Analysis for {self.resume.user.email} ({self.status})"
