import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("resumes", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ResumeIndex",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("indexed", "Indexed"), ("failed", "Failed")],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("chunk_count", models.PositiveIntegerField(default=0)),
                ("content_hash", models.CharField(blank=True, max_length=64)),
                ("error_message", models.TextField(blank=True)),
                ("indexed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "resume",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="rag_index",
                        to="resumes.resume",
                    ),
                ),
            ],
        ),
    ]
