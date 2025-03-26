from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.http import HttpResponse

from .models import Analysis
from .forms import CreateAnalysisForm
from .services import AnalysisService
from apps.advisories.models import Advisory


class AnalysisListView(ListView):
    """View to display a list of analyses"""
    
    model = Analysis
    template_name = 'analysis/analysis_list.html'
    context_object_name = 'analyses'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Analysis.objects.all()
        
        # Filter by vuln_type if provided
        vuln_type = self.request.GET.get('type')
        if vuln_type:
            queryset = queryset.filter(vuln_type=vuln_type)
        
        # Filter by poc_feasibility if provided
        poc_min = self.request.GET.get('poc_min')
        if poc_min and poc_min.isdigit():
            queryset = queryset.filter(poc_feasibility__gte=int(poc_min))
            
        poc_max = self.request.GET.get('poc_max')
        if poc_max and poc_max.isdigit():
            queryset = queryset.filter(poc_feasibility__lte=int(poc_max))
        
        # Sort by requested field
        sort_by = self.request.GET.get('sort', '-created_at')
        if sort_by not in ['-created_at', 'created_at', 'poc_feasibility', '-poc_feasibility', 
                          'patch_effectiveness', '-patch_effectiveness']:
            sort_by = '-created_at'
        
        return queryset.order_by(sort_by)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get filter values
        context['current_type'] = self.request.GET.get('type', '')
        context['current_poc_min'] = self.request.GET.get('poc_min', '')
        context['current_poc_max'] = self.request.GET.get('poc_max', '')
        context['current_sort'] = self.request.GET.get('sort', '-created_at')
        
        # Get distinct vulnerability types
        context['vulnerability_types'] = Analysis.objects.values_list(
            'vuln_type', flat=True
        ).distinct()
        
        # Get available complexity options
        context['complexity_choices'] = [choice[0] for choice in Analysis.COMPLEXITY_CHOICES]
        
        return context


class AnalysisDetailView(DetailView):
    """View to display a single analysis"""
    
    model = Analysis
    template_name = 'analysis/analysis_detail.html'
    context_object_name = 'analysis'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['advisory'] = self.object.advisory
        context['commits'] = self.object.advisory.commits.all()
        return context


class AnalysisReportView(DetailView):
    """View to display an analysis report in various formats"""
    
    model = Analysis
    template_name = 'analysis/analysis_report.html'
    context_object_name = 'analysis'
    
    def get(self, request, *args, **kwargs):
        analysis = self.get_object()
        
        # Check if a download format is requested
        format_type = request.GET.get('format')
        if format_type == 'markdown' and analysis.markdown_report:
            response = HttpResponse(analysis.markdown_report, content_type='text/markdown')
            response['Content-Disposition'] = f'attachment; filename="{analysis.advisory.github_id}_analysis.md"'
            return response
        elif format_type == 'html' and analysis.html_report:
            response = HttpResponse(analysis.html_report, content_type='text/html')
            response['Content-Disposition'] = f'attachment; filename="{analysis.advisory.github_id}_analysis.html"'
            return response
        
        return super().get(request, *args, **kwargs)


class CreateAnalysisView(LoginRequiredMixin, TemplateView):
    """View to create a new analysis for an advisory"""
    
    template_name = 'analysis/create_analysis.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        github_id = kwargs.get('github_id')
        advisory = get_object_or_404(Advisory, github_id=github_id)
        
        context['advisory'] = advisory
        context['form'] = CreateAnalysisForm()
        context['existing_analyses'] = Analysis.objects.filter(advisory=advisory)
        
        # Add commits to the context - this was missing
        context['commits'] = advisory.commits.all()
        
        return context
    
    def post(self, request, *args, **kwargs):
        github_id = kwargs.get('github_id')
        advisory = get_object_or_404(Advisory, github_id=github_id)
        form = CreateAnalysisForm(request.POST)
        
        if form.is_valid():
            model = form.cleaned_data.get('model')
            
            # Get API key from user profile if available
            api_key = None
            if hasattr(request.user, 'profile'):
                api_key = request.user.profile.openai_api_key
            
            service = AnalysisService(api_key=api_key, user=request.user)
            analysis = service.analyze_advisory(advisory, model=model)
            
            if analysis:
                messages.success(request, f"Analysis created successfully for {github_id}")
                return redirect('analysis-detail', pk=analysis.id)
            else:
                messages.error(request, "Failed to create analysis. Please check logs for details.")
        
        # If we get here, there was an error
        context = self.get_context_data(**kwargs)
        context['form'] = form
        return render(request, self.template_name, context)