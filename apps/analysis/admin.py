from django.contrib import admin
from .models import Analysis


@admin.register(Analysis)
class AnalysisAdmin(admin.ModelAdmin):
    """Admin configuration for Analysis model"""
    
    list_display = ('get_github_id', 'vuln_type', 'poc_feasibility', 'patch_effectiveness', 'poc_complexity', 'created_at')
    list_filter = ('poc_complexity', 'created_at')
    search_fields = ('advisory__github_id', 'vuln_type', 'vuln_explanation')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    raw_id_fields = ('advisory', 'user')
    
    fieldsets = (
        (None, {
            'fields': ('advisory', 'user', 'model_used')
        }),
        ('Classification', {
            'fields': ('vuln_type', 'patch_effectiveness', 'poc_feasibility', 'poc_complexity')
        }),
        ('Analysis', {
            'fields': ('vuln_explanation', 'patch_analysis', 'impact_summary')
        }),
        ('PoC Details', {
            'fields': ('required_skills', 'information_gaps', 'key_indicators')
        }),
        ('Reports', {
            'fields': ('markdown_report', 'html_report')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def get_github_id(self, obj):
        """Get the advisory's GitHub ID"""
        return obj.advisory.github_id
    get_github_id.short_description = 'Advisory ID'
    get_github_id.admin_order_field = 'advisory__github_id'