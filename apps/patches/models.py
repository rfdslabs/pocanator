from django.db import models
from apps.advisories.models import Commit


class FileChange(models.Model):
    """Model representing a file change in a commit"""
    
    commit = models.ForeignKey(Commit, on_delete=models.CASCADE, related_name='file_changes')
    file_path = models.CharField(max_length=512, help_text="Path of the changed file")
    is_binary = models.BooleanField(default=False, help_text="Whether the file is binary")
    lines_added = models.IntegerField(default=0, help_text="Number of lines added")
    lines_removed = models.IntegerField(default=0, help_text="Number of lines removed")
    
    class Meta:
        verbose_name = "File Change"
        verbose_name_plural = "File Changes"
        ordering = ['file_path']
    
    def __str__(self):
        return f"{self.file_path} (+{self.lines_added}/-{self.lines_removed})"
        
    def get_old_content(self):
        """Get the old content of the file by collecting context and remove lines"""
        old_lines = []
        for line in self.line_changes.filter(change_type__in=['context', 'remove']).order_by('old_line_num'):
            old_lines.append(line.content)
        return "\n".join(old_lines)
    
    def get_new_content(self):
        """Get the new content of the file by collecting context and add lines"""
        new_lines = []
        for line in self.line_changes.filter(change_type__in=['context', 'add']).order_by('new_line_num'):
            new_lines.append(line.content)
        return "\n".join(new_lines)


class LineChange(models.Model):
    """Model representing a single line change"""
    
    CHANGE_TYPES = [
        ('add', 'Addition'),
        ('remove', 'Removal'),
        ('context', 'Context'),
    ]
    
    file_change = models.ForeignKey(FileChange, on_delete=models.CASCADE, related_name='line_changes')
    change_type = models.CharField(max_length=10, choices=CHANGE_TYPES)
    old_line_num = models.IntegerField(null=True, blank=True, help_text="Old line number")
    new_line_num = models.IntegerField(null=True, blank=True, help_text="New line number")
    content = models.TextField(help_text="Content of the line")
    
    class Meta:
        verbose_name = "Line Change"
        verbose_name_plural = "Line Changes"
        ordering = ['old_line_num', 'new_line_num']
    
    def __str__(self):
        prefix = {
            'add': '+',
            'remove': '-',
            'context': ' ',
        }.get(self.change_type, ' ')
        
        line_num = self.new_line_num if self.new_line_num else self.old_line_num
        return f"{line_num}: {prefix}{self.content[:50]}"
    
    @property
    def line_class(self):
        """Return CSS class based on change type"""
        return {
            'add': 'diff-add',
            'remove': 'diff-remove',
            'context': '',
        }.get(self.change_type, '')