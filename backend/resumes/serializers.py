from django.conf import settings
from rest_framework import serializers

from .models import Resume

PDF_MAGIC_BYTES = b"%PDF-"


class ResumeUploadSerializer(serializers.Serializer):
    """Validates an incoming PDF upload. Does not itself create the Resume —
    the view handles that after also running text extraction, so a failed
    extraction never leaves a half-written record behind."""

    file = serializers.FileField()

    def validate_file(self, uploaded_file):
        max_bytes = settings.MAX_RESUME_SIZE_MB * 1024 * 1024
        if uploaded_file.size > max_bytes:
            raise serializers.ValidationError(
                f"File is too large. Maximum size is {settings.MAX_RESUME_SIZE_MB}MB."
            )
        if uploaded_file.size == 0:
            raise serializers.ValidationError("File is empty.")

        name = (uploaded_file.name or "").lower()
        if not name.endswith(".pdf"):
            raise serializers.ValidationError("Only PDF files are accepted.")

        content_type = getattr(uploaded_file, "content_type", "") or ""
        if content_type not in ("application/pdf", "application/x-pdf"):
            raise serializers.ValidationError("Only PDF files are accepted.")

        # Client-supplied extension/content-type can both be spoofed — check
        # the actual file signature too before we trust it's really a PDF.
        header = uploaded_file.read(len(PDF_MAGIC_BYTES))
        uploaded_file.seek(0)
        if header != PDF_MAGIC_BYTES:
            raise serializers.ValidationError("This file does not look like a valid PDF.")

        return uploaded_file


class ResumeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resume
        fields = [
            "id",
            "original_filename",
            "file_size",
            "page_count",
            "status",
            "extracted_text",
            "uploaded_at",
            "processed_at",
        ]
        read_only_fields = fields
