from rest_framework import serializers

from assistant.models import InterviewSession

from .models import InterviewChatMessage


class InterviewHistoryListSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    overall_score = serializers.SerializerMethodField()
    question_count = serializers.SerializerMethodField()
    # "date" is when the interview was completed, not last touched — see
    # the rename view, which deliberately avoids bumping updated_at.
    date = serializers.DateTimeField(source="updated_at")

    class Meta:
        model = InterviewSession
        fields = ["id", "title", "role", "status", "overall_score", "question_count", "date"]

    def get_title(self, obj):
        return obj.title or obj.role

    def get_overall_score(self, obj):
        return obj.final_report.get("overall_score") if obj.final_report else None

    def get_question_count(self, obj):
        return len(obj.questions)


class InterviewHistoryDetailSerializer(InterviewHistoryListSerializer):
    class Meta(InterviewHistoryListSerializer.Meta):
        fields = InterviewHistoryListSerializer.Meta.fields + ["questions", "qa_log", "final_report"]


class InterviewChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterviewChatMessage
        fields = ["id", "role", "content", "created_at"]
        read_only_fields = fields
