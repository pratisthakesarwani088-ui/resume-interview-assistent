from django.contrib import admin

from .models import ResumeIndex


@admin.register(ResumeIndex)
class ResumeIndexAdmin(admin.ModelAdmin):
    list_display = ["resume", "status", "chunk_count", "indexed_at"]
    list_filter = ["status"]
    search_fields = ["resume__user__email"]
    readonly_fields = [f.name for f in ResumeIndex._meta.fields]

    def has_add_permission(self, request):
        # Index records are only ever created by the indexing pipeline itself.
        return False
