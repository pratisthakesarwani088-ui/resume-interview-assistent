from django.contrib import admin

from .models import ChatMessage, ChatSession, InterviewSession


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ["role", "content", "created_at"]
    can_delete = False


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ["user", "mode", "selected_role", "updated_at"]
    list_filter = ["mode"]
    search_fields = ["user__email"]
    readonly_fields = ["user", "mode", "selected_role", "created_at", "updated_at"]
    inlines = [ChatMessageInline]

    def has_add_permission(self, request):
        return False


@admin.register(InterviewSession)
class InterviewSessionAdmin(admin.ModelAdmin):
    list_display = ["user", "role", "status", "current_question_index", "created_at"]
    list_filter = ["status"]
    search_fields = ["user__email", "role"]
    readonly_fields = [f.name for f in InterviewSession._meta.fields]

    def has_add_permission(self, request):
        return False
