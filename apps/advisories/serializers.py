from rest_framework import serializers
from .models import Advisory, Commit


class CommitSerializer(serializers.ModelSerializer):
    """Serializer for Commit model"""
    short_hash = serializers.SerializerMethodField()
    
    class Meta:
        model = Commit
        fields = [
            'id', 'repo_name', 'commit_hash', 'short_hash', 'commit_url',
            'lines_added', 'lines_removed', 'fetch_date'
        ]
    
    def get_short_hash(self, obj):
        return obj.commit_hash[:7] if obj.commit_hash else ''


class AdvisorySerializer(serializers.ModelSerializer):
    """Serializer for Advisory model"""
    commits = CommitSerializer(many=True, read_only=True)
    has_analysis = serializers.SerializerMethodField()
    severity_class = serializers.CharField(source='get_severity_display', read_only=True)
    
    class Meta:
        model = Advisory
        fields = [
            'id', 'github_id', 'url', 'title', 'description', 
            'severity', 'severity_class', 'cve_id', 'cvss_score', 
            'vulnerability_type', 'affected_versions', 
            'published_date', 'discovered_date', 
            'has_analysis', 'commits'
        ]
    
    def get_has_analysis(self, obj):
        return obj.analyses.exists()