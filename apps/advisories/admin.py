from django.contrib import admin
from .models import Advisory, Commit


@admin.register(Advisory)
class AdvisoryAdmin(admin.ModelAdmin):
    """Admin configuration for Advisory model"""
    
    list_display = ('github_id', 'title', 'severity', 'vulnerability_type', 'cve_id', 'discovered_date')
    list_filter = ('severity', 'vulnerability_type')
    search_fields = ('github_id', 'title', 'description', 'cve_id')
    readonly_fields = ('discovered_date',)
    date_hierarchy = 'discovered_date'
    
    fieldsets = (
        (None, {
            'fields': ('github_id', 'url', 'title', 'severity')
        }),
        ('Details', {
            'fields': ('description', 'vulnerability_type', 'affected_versions')
        }),
        ('References', {
            'fields': ('cve_id', 'cvss_score')
        }),
        ('Dates', {
            'fields': ('published_date', 'discovered_date')
        }),
    )


@admin.register(Commit)
class CommitAdmin(admin.ModelAdmin):
    """Admin configuration for Commit model"""
    
    list_display = ('get_github_id', 'repo_name', 'short_hash', 'files_changed', 'lines_added', 'lines_removed', 'fetch_date')
    list_filter = ('fetch_date',)
    search_fields = ('advisory__github_id', 'repo_name', 'commit_hash')
    readonly_fields = ('fetch_date', 'files_changed')
    date_hierarchy = 'fetch_date'
    raw_id_fields = ('advisory',)
    
    fieldsets = (
        (None, {
            'fields': ('advisory', 'repo_name', 'commit_hash')
        }),
        ('URLs', {
            'fields': ('commit_url',)
        }),
        ('Diff', {
            'fields': ('diff_text', 'lines_added', 'lines_removed')
        }),
        ('Metadata', {
            'fields': ('fetch_date',)
        }),
    )
    
    def get_github_id(self, obj):
        """Get the advisory's GitHub ID"""
        return obj.advisory.github_id
    get_github_id.short_description = 'Advisory ID'
    get_github_id.admin_order_field = 'advisory__github_id'
    
    def short_hash(self, obj):
        """Get the short commit hash"""
        return obj.commit_hash[:7] if obj.commit_hash else ''
    short_hash.short_description = 'Commit'