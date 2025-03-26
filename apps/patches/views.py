from django.shortcuts import render, get_object_or_404
from django.views.generic import DetailView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

from .models import FileChange, LineChange
from apps.advisories.models import Advisory, Commit


class CommitDetailView(DetailView):
    """View to display commit details"""
    model = Commit
    template_name = 'patches/commit_detail.html'
    context_object_name = 'commit'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['file_changes'] = self.object.file_changes.all()
        return context


class FileChangeDetailView(DetailView):
    """View to display file change details"""
    model = FileChange
    template_name = 'patches/file_change_detail.html'
    context_object_name = 'file_change'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['line_changes'] = self.object.line_changes.all()
        return context


class VisualDiffView(LoginRequiredMixin, TemplateView):
    """View to display an interactive visualization of the diff"""
    template_name = 'patches/visual_diff.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        advisory_id = self.kwargs.get('advisory_id')
        advisory = get_object_or_404(Advisory, id=advisory_id)
        
        context['advisory'] = advisory
        context['commits'] = advisory.commits.all()
        
        # Get file changes for each commit
        commit_data = []
        for commit in context['commits']:
            commit_data.append({
                'commit': commit,
                'file_changes': commit.file_changes.all()
            })
        
        context['commit_data'] = commit_data
        return context