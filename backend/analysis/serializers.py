from rest_framework import serializers

from .models import ResumeAnalysis


class ResumeAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResumeAnalysis
        fields = [
            "id",
            "status",
            "ats_score",
            "strengths",
            "weaknesses",
            "extracted_skills",
            "projects_experience",
            "suggested_roles",
            "improvement_suggestions",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
