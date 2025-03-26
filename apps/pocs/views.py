from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import reverse
from django.contrib import messages
from django.conf import settings
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import ProofOfConcept, PoCTemplate
from .forms import PoCRequestForm
from apps.analysis.models import Analysis
from .services.generation_service import PoCGenerationService
from .services.feedback_learning_service import PoCFeedbackLearningService
import time
import logging
import json

logger = logging.getLogger(__name__)

# Initialize the services
poc_generator = PoCGenerationService(api_key=getattr(settings, 'OPENAI_API_KEY', None))
feedback_service = PoCFeedbackLearningService()

@login_required
def request_poc(request, analysis_id):
    """View to handle PoC generation requests"""
    analysis = get_object_or_404(Analysis, pk=analysis_id)
    
    # Check if there's already a PoC for this analysis by this user
    existing_poc = ProofOfConcept.objects.filter(
        analysis=analysis,
        user=request.user
    ).first()
    
    if existing_poc:
        messages.info(request, "You already have a PoC for this analysis.")
        return redirect('view_poc', poc_id=existing_poc.id)
    
    if request.method == 'POST':
        form = PoCRequestForm(request.POST)
        if form.is_valid():
            # Create a new PoC request
            poc = form.save(commit=False)
            poc.analysis = analysis
            poc.user = request.user
            poc.status = 'requested'
            poc.save()
            
            try:
                # Start the generation process asynchronously
                logger.info(f"Starting async PoC generation for ID {poc.id}")
                poc_generator.generate_poc_async(poc.id)
                messages.success(request, "PoC generation started. You'll be notified when it's ready.")
            except Exception as e:
                logger.error(f"Error starting PoC generation: {str(e)}")
                messages.error(request, "There was an error starting the PoC generation. Please try again later.")
            
            return redirect('poc_status', poc_id=poc.id)
    else:
        form = PoCRequestForm()
    
    return render(request, 'pocs/request_form.html', {
        'form': form,
        'analysis': analysis
    })

@login_required
def poc_status(request, poc_id):
    """View to display the status of a PoC generation request"""
    poc = get_object_or_404(ProofOfConcept, pk=poc_id)
    
    # Ensure user has access
    if poc.user != request.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to view this PoC.")
        return redirect('analysis-detail', analysis_id=poc.analysis.id)
    
    return render(request, 'pocs/status.html', {
        'poc': poc
    })

@login_required
def poc_status_api(request, poc_id):
    """API endpoint for checking PoC generation status"""
    poc = get_object_or_404(ProofOfConcept, pk=poc_id)
    
    # Ensure user has access
    if poc.user != request.user and not request.user.is_staff:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    # Return the current status from the database
    # (The generation service updates this in the background)
    data = {
        'status': poc.status,
        'created_at': poc.created_at.isoformat(),
        'updated_at': poc.updated_at.isoformat(),
    }
    
    if poc.status == 'completed':
        data['completion_time'] = poc.completion_time
        data['tokens_used'] = poc.tokens_used
        
    elif poc.status == 'failed':
        data['error'] = "The PoC generation process failed. Please try again or contact support."
    
    return JsonResponse(data)

@login_required
def view_poc(request, poc_id):
    """View to display a generated PoC"""
    poc = get_object_or_404(ProofOfConcept, pk=poc_id)
    
    # Ensure user has access
    if poc.user != request.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to view this PoC.")
        return redirect('analysis-detail', analysis_id=poc.analysis.id)
    
    if poc.status != 'completed':
        return redirect('poc_status', poc_id=poc.id)
    
    return render(request, 'pocs/detail.html', {
        'poc': poc
    })

@login_required
def poc_feedback(request, poc_id):
    """View to handle PoC feedback submission with enhanced learning"""
    poc = get_object_or_404(ProofOfConcept, pk=poc_id)
    
    # Ensure user has access
    if poc.user != request.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to submit feedback for this PoC.")
        return redirect('analysis-detail', analysis_id=poc.analysis.id)
    
    if request.method == 'POST':
        worked = request.POST.get('worked_as_expected')
        feedback = request.POST.get('user_feedback')
        effectiveness_score = request.POST.get('effectiveness_score')
        
        changes_made = False
        
        if worked in ['true', 'false']:
            poc.worked_as_expected = (worked == 'true')
            changes_made = True
            
        if feedback:
            poc.user_feedback = feedback
            changes_made = True
            
        if effectiveness_score and effectiveness_score.isdigit():
            score = int(effectiveness_score)
            if 1 <= score <= 10:  # Validate the score range
                poc.effectiveness_score = score
                changes_made = True
        
        if changes_made:
            poc.save()
            
            # Process feedback for learning
            try:
                logger.info(f"Processing feedback learning for PoC {poc_id}")
                feedback_service.process_new_feedback(poc_id)
                
                # If this is a highly rated PoC, consider creating a new template
                if poc.worked_as_expected and poc.effectiveness_score and poc.effectiveness_score >= 8:
                    logger.info(f"Attempting to learn new template from successful PoC {poc_id}")
                    template = feedback_service.generate_improved_template_from_success(poc_id)
                    if template:
                        logger.info(f"Created new template {template.id} from PoC {poc_id}")
                
                # If this PoC used a template, update its metrics
                if poc.template_used:
                    logger.info(f"Updating metrics for template {poc.template_used.id}")
                    poc.template_used.update_metrics(poc.effectiveness_score, poc.worked_as_expected)
                    
                    # Apply feedback improvements to the template
                    if not poc.worked_as_expected or (poc.effectiveness_score and poc.effectiveness_score < 7):
                        feedback_service.apply_feedback_improvements(poc.template_used)
            except Exception as e:
                logger.error(f"Error processing feedback learning: {str(e)}")
            
            messages.success(request, "Thank you for your feedback! Your input helps improve future generations.")
        
    return redirect('view_poc', poc_id=poc.id)


@login_required
def regenerate_poc(request, poc_id):
    """View to regenerate a PoC while preserving history"""
    original_poc = get_object_or_404(ProofOfConcept, pk=poc_id)
    
    # Ensure user has access
    if original_poc.user != request.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to regenerate this PoC.")
        return redirect('analysis-detail', analysis_id=original_poc.analysis.id)
    
    # Can only regenerate completed PoCs
    if original_poc.status != 'completed':
        messages.error(request, "Cannot regenerate a PoC that isn't completed.")
        return redirect('poc_status', poc_id=original_poc.id)
    
    try:
        # Create a new PoC record with the same parameters but linked to the original
        new_poc = ProofOfConcept(
            analysis=original_poc.analysis,
            user=request.user,
            status='requested',
            target_os=original_poc.target_os,
            target_language_version=original_poc.target_language_version,
            exploitation_goal=original_poc.exploitation_goal,
            use_deep_thinking=original_poc.use_deep_thinking,
            additional_context=original_poc.additional_context,
            previous_version=original_poc  # Link to previous version
        )
        new_poc.save()
        
        # Start generation process
        logger.info(f"Starting regeneration for PoC {new_poc.id} (previous version: {poc_id})")
        poc_generator.generate_poc_async(new_poc.id)
        
        messages.success(request, "PoC regeneration started. The previous version will be preserved for comparison.")
        return redirect('poc_status', poc_id=new_poc.id)
        
    except Exception as e:
        logger.error(f"Error regenerating PoC {poc_id}: {str(e)}")
        messages.error(request, "There was an error regenerating the PoC. Please try again later.")
        return redirect('view_poc', poc_id=poc_id)

@login_required
def delete_poc(request, poc_id):
    """View to delete a PoC"""
    poc = get_object_or_404(ProofOfConcept, pk=poc_id)
    
    # Ensure user has access
    if poc.user != request.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to delete this PoC.")
        return redirect('analysis-detail', analysis_id=poc.analysis.id)
    
    analysis_id = poc.analysis.id
    
    if request.method == 'POST':
        try:
            # Check if this PoC has next versions (regenerated from this one)
            if poc.next_versions.exists():
                # Update next versions to point to this PoC's previous version
                for next_version in poc.next_versions.all():
                    next_version.previous_version = poc.previous_version
                    next_version.save()
            
            # Delete the PoC
            poc.delete()
            messages.success(request, "PoC successfully deleted.")
            
            # Redirect to analysis page
            return redirect('analysis-detail', analysis_id=analysis_id)
            
        except Exception as e:
            logger.error(f"Error deleting PoC {poc_id}: {str(e)}")
            messages.error(request, "There was an error deleting the PoC. Please try again later.")
            return redirect('view_poc', poc_id=poc_id)
    
    # Show confirmation page for GET requests
    return render(request, 'pocs/confirm_delete.html', {
        'poc': poc
    })

@login_required
def poc_history(request, poc_id):
    """View to show a PoC's history/versions"""
    poc = get_object_or_404(ProofOfConcept, pk=poc_id)
    
    # Ensure user has access
    if poc.user != request.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to view this PoC's history.")
        return redirect('analysis-detail', analysis_id=poc.analysis.id)
    
    # Find the original version by traversing previous_version links
    original_poc = poc
    while original_poc.previous_version:
        original_poc = original_poc.previous_version
    
    # Get all versions in order
    versions = []
    current = original_poc
    while current:
        versions.append(current)
        # Get the next version (there should only be one in a linear history)
        try:
            current = current.next_versions.first()
        except:
            current = None
    
    return render(request, 'pocs/history.html', {
        'current_poc': poc,
        'versions': versions
    })

class PoCListView(LoginRequiredMixin, ListView):
    """View to list all proofs of concept"""
    model = ProofOfConcept
    template_name = 'pocs/list.html'
    context_object_name = 'pocs'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = ProofOfConcept.objects.all()
        
        # Filter by status if provided
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by user if not staff
        if not self.request.user.is_staff:
            queryset = queryset.filter(user=self.request.user)
            
        # Filter by vulnerability type if provided
        vuln_type = self.request.GET.get('vuln_type')
        if vuln_type:
            queryset = queryset.filter(analysis__vuln_type=vuln_type)
            
        # Filter by language if provided
        language = self.request.GET.get('language')
        if language:
            queryset = queryset.filter(language=language)
        
        # Sort by
        sort_by = self.request.GET.get('sort', '-created_at')
        if sort_by not in ['-created_at', 'created_at', '-updated_at', 'updated_at']:
            sort_by = '-created_at'
            
        return queryset.order_by(sort_by)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get filter values
        context['current_status'] = self.request.GET.get('status', '')
        context['current_vuln_type'] = self.request.GET.get('vuln_type', '')
        context['current_language'] = self.request.GET.get('language', '')
        context['current_sort'] = self.request.GET.get('sort', '-created_at')
        
        # Get distinct values for filters
        context['vulnerability_types'] = Analysis.objects.values_list(
            'vuln_type', flat=True
        ).distinct().order_by('vuln_type')
        
        context['languages'] = ProofOfConcept.objects.exclude(
            language__isnull=True
        ).exclude(
            language=''
        ).values_list(
            'language', flat=True
        ).distinct().order_by('language')
        
        # Get status choices
        context['status_choices'] = [choice[0] for choice in ProofOfConcept.STATUS_CHOICES]
        
        return context