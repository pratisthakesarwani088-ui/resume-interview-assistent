from django.core.management.base import BaseCommand

from rag.models import ResumeIndex
from rag.services import RAGError, index_resume
from resumes.models import Resume


class Command(BaseCommand):
    help = (
        "Indexes into ChromaDB any processed resume that isn't indexed yet — "
        "covers resumes uploaded before this module existed, or ones whose "
        "automatic indexing previously failed. Already-indexed resumes are "
        "skipped (index_resume is idempotent), so this is safe to re-run."
    )

    def handle(self, *args, **options):
        processed = Resume.objects.filter(status=Resume.STATUS_PROCESSED)
        indexed_count = 0
        skipped_count = 0
        failed_count = 0

        for resume in processed:
            existing = ResumeIndex.objects.filter(resume=resume).first()
            if existing and existing.status == ResumeIndex.STATUS_INDEXED:
                skipped_count += 1
                continue
            try:
                index_resume(resume)
                indexed_count += 1
                self.stdout.write(f"Indexed resume id={resume.id} (user={resume.user.email})")
            except RAGError as exc:
                failed_count += 1
                self.stderr.write(f"Failed to index resume id={resume.id}: {exc}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Indexed: {indexed_count}, already up to date: {skipped_count}, failed: {failed_count}."
            )
        )
