from django.contrib import admin
from .models import FileChange, LineChange


@admin.register(FileChange)
class FileChangeAdmin(admin.ModelAdmin):
    """Admin configuration for FileChange model"""
    
    list_display = ('get_commit_id', 'file_path', 'lines_added', 'lines_removed', 'is_binary')
    list_filter = ('is_binary',)
    search_fields = ('commit__advisory__github_id', 'file_path')
    raw_id_fields = ('commit',)
    
    def get_commit_id(self, obj):
        """Get the commit's short hash"""
        return f"{obj.commit.advisory.github_id}: {obj.commit.commit_hash[:7]}"
    get_commit_id.short_description = 'Commit'


@admin.register(LineChange)
class LineChangeAdmin(admin.ModelAdmin):
    """Admin configuration for LineChange model"""
    
    list_display = ('get_file_path', 'change_type', 'old_line_num', 'new_line_num', 'get_content_preview')
    list_filter = ('change_type',)
    search_fields = ('file_change__file_path', 'content')
    raw_id_fields = ('file_change',)
    
    def get_file_path(self, obj):
        """Get the file path"""
        return obj.file_change.file_path
    get_file_path.short_description = 'File Path'
    
    def get_content_preview(self, obj):
        """Get a preview of the content"""
        if len(obj.content) > 50:
            return f"{obj.content[:50]}..."
        return obj.content
    get_content_preview.short_description = 'Content'