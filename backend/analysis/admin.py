from django.contrib import admin

from .models import ResumeAnalysis


@admin.register(ResumeAnalysis)
class ResumeAnalysisAdmin(admin.ModelAdmin):
    list_display = ["resume", "status", "ats_score", "created_at", "updated_at"]
    list_filter = ["status"]
    search_fields = ["resume__user__email"]
    readonly_fields = [f.name for f in ResumeAnalysis._meta.fields]

    def has_add_permission(self, request):
        # Analyses are only ever created through the API (they require a live
        # Gemini call), never hand-entered in the admin.
        return False
