import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("resumes", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ResumeAnalysis",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("completed", "Completed"), ("failed", "Failed")],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("ats_score", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("strengths", models.JSONField(blank=True, default=list)),
                ("weaknesses", models.JSONField(blank=True, default=list)),
                ("extracted_skills", models.JSONField(blank=True, default=list)),
                ("projects_experience", models.JSONField(blank=True, default=list)),
                ("suggested_roles", models.JSONField(blank=True, default=list)),
                ("improvement_suggestions", models.JSONField(blank=True, default=list)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "resume",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="analysis",
                        to="resumes.resume",
                    ),
                ),
            ],
        ),
    ]
