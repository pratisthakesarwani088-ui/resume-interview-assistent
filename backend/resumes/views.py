from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Resume
from .serializers import ResumeSerializer, ResumeUploadSerializer
from .services import PDFExtractionError, extract_text_from_pdf


class ResumeUploadView(APIView):
    """
    POST /api/resumes/upload/  (multipart, field name "file")

    Rejects if the user already has a resume — this module intentionally has
    no replace/delete flow, so a second upload is a 409, not an overwrite.
    """

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request):
        if Resume.objects.filter(user=request.user).exists():
            return Response(
                {"detail": "You've already uploaded a resume. Replacing resumes isn't supported."},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = ResumeUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uploaded_file = serializer.validated_data["file"]

        with transaction.atomic():
            resume = Resume.objects.create(
                user=request.user,
                file=uploaded_file,
                original_filename=uploaded_file.name,
                file_size=uploaded_file.size,
                status=Resume.STATUS_PENDING,
            )

        try:
            text, page_count = extract_text_from_pdf(resume.file.path)
        except PDFExtractionError as exc:
            # Don't leave a broken half-processed record or an orphan file.
            resume.file.delete(save=False)
            resume.delete()
            return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        resume.extracted_text = text
        resume.page_count = page_count
        resume.status = Resume.STATUS_PROCESSED
        resume.processed_at = timezone.now()
        resume.save(update_fields=["extracted_text", "page_count", "status", "processed_at"])

        return Response(ResumeSerializer(resume).data, status=status.HTTP_201_CREATED)


class ResumeStatusView(APIView):
    """
    GET /api/resumes/me/  -> always scoped to request.user, never a pk lookup,
    so one user can never fetch another user's resume.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        resume = Resume.objects.filter(user=request.user).first()
        if not resume:
            return Response({"has_resume": False})
        return Response({"has_resume": True, "resume": ResumeSerializer(resume).data})
