from django.contrib import admin

from .models import InterviewChatMessage


@admin.register(InterviewChatMessage)
class InterviewChatMessageAdmin(admin.ModelAdmin):
    list_display = ["interview", "role", "created_at"]
    list_filter = ["role"]
    search_fields = ["interview__user__email", "interview__role"]
    readonly_fields = ["interview", "role", "content", "created_at"]

    def has_add_permission(self, request):
        return False
