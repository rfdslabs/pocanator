from django.contrib import admin
from .models import ProofOfConcept, PoCTemplate, PoCFeedbackAnalysis

@admin.register(ProofOfConcept)
class ProofOfConceptAdmin(admin.ModelAdmin):
    list_display = ('id', 'analysis', 'target_os', 'status', 'user', 'created_at', 'worked_as_expected', 'effectiveness_score')
    list_filter = ('status', 'target_os', 'use_deep_thinking', 'worked_as_expected')
    search_fields = ('analysis__advisory__github_id', 'user__username')
    readonly_fields = ('created_at', 'updated_at', 'completion_time', 'tokens_used')
    fieldsets = (
        ('Relationship', {
            'fields': ('analysis', 'user', 'template_used')
        }),
        ('Status', {
            'fields': ('status', 'created_at', 'updated_at', 'completion_time', 'tokens_used')
        }),
        ('Configuration', {
            'fields': ('target_os', 'target_language_version', 'exploitation_goal', 
                      'use_deep_thinking', 'additional_context')
        }),
        ('Results', {
            'fields': ('code', 'language', 'explanation', 'setup_instructions', 'security_warnings')
        }),
        ('Feedback', {
            'fields': ('user_feedback', 'worked_as_expected', 'effectiveness_score', 'feedback_categories')
        }),
    )

@admin.register(PoCTemplate)
class PoCTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'vulnerability_type', 'usage_count', 'success_count', 'success_rate', 'average_effectiveness', 'is_active')
    list_filter = ('vulnerability_type', 'is_active')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at', 'usage_count', 'success_count', 'average_effectiveness')
    fieldsets = (
        ('Template Information', {
            'fields': ('name', 'vulnerability_type', 'description', 'is_active')
        }),
        ('Prompt Content', {
            'fields': ('system_prompt', 'user_prompt_template', 'code_skeleton')
        }),
        ('Performance Metrics', {
            'fields': ('usage_count', 'success_count', 'average_effectiveness', 'created_at', 'updated_at')
        }),
    )

@admin.register(PoCFeedbackAnalysis)
class PoCFeedbackAnalysisAdmin(admin.ModelAdmin):
    list_display = ('vulnerability_type', 'feedback_category', 'sample_size', 'confidence_score', 'last_updated')
    list_filter = ('vulnerability_type', 'feedback_category')
    search_fields = ('vulnerability_type', 'feedback_category', 'common_issues', 'suggested_improvements')
    readonly_fields = ('last_updated',)
    fieldsets = (
        ('Classification', {
            'fields': ('vulnerability_type', 'feedback_category')
        }),
        ('Analysis', {
            'fields': ('common_issues', 'suggested_improvements', 'affected_prompt_sections')
        }),
        ('Metadata', {
            'fields': ('sample_size', 'confidence_score', 'last_updated')
        }),
    )