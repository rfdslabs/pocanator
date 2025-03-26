from rest_framework import serializers
from .models import Analysis


class AnalysisSerializer(serializers.ModelSerializer):
    """Serializer for Analysis model"""
    advisory_id = serializers.CharField(source='advisory.github_id', read_only=True)
    
    class Meta:
        model = Analysis
        fields = [
            'id', 'advisory', 'advisory_id', 'user', 'model_used',
            'vuln_type', 'vuln_explanation', 'patch_analysis', 'impact_summary',
            'patch_effectiveness', 'poc_feasibility', 'poc_complexity',
            'required_skills', 'information_gaps', 'key_indicators',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class AnalysisCreateSerializer(serializers.Serializer):
    """Serializer for creating a new analysis"""
    advisory = serializers.IntegerField()
    model = serializers.CharField(required=False, default='gpt-4o')
    api_key = serializers.CharField(required=False, allow_null=True, allow_blank=True)