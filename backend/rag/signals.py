import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from resumes.models import Resume

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Resume)
def index_resume_on_processed(sender, instance, **kwargs):
    """Runs automatically whenever a Resume is saved with status=processed
    (i.e. right after Module 2 finishes PDF extraction). Indexing failures
    are logged and recorded on the ResumeIndex row, never raised here — a
    RAG hiccup must not be able to break the resume upload response."""
    if instance.status != Resume.STATUS_PROCESSED:
        return

    from .services import RAGError, index_resume  # local import avoids app-loading order issues

    try:
        index_resume(instance)
    except RAGError:
        logger.exception("RAG indexing failed for resume id=%s", instance.id)
