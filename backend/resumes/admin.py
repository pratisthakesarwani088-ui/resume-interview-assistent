from django.contrib import admin

from .models import Resume


@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = ["user", "original_filename", "status", "page_count", "uploaded_at"]
    list_filter = ["status"]
    search_fields = ["user__email", "original_filename"]
    readonly_fields = [
        "user",
        "file",
        "original_filename",
        "file_size",
        "extracted_text",
        "page_count",
        "status",
        "uploaded_at",
        "processed_at",
    ]

    def has_add_permission(self, request):
        # Uploads only happen through the API (extraction must run alongside).
        return False
