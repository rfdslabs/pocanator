# PoC Generation System: Implementation Guide

## Overview

This guide outlines the step-by-step implementation plan for the Proof of Concept (PoC) Generation System. The implementation is divided into phases, with each phase building upon the previous one to create a complete, integrated system.

## Phase 1: Core Data Models and Request Flow

The focus of Phase 1 is to establish the foundational data models and basic request flow, enabling the storage and tracking of PoC generation requests.

### Step 1: Create the Core Data Model

1. Create the `ProofOfConcept` model in a new file `apps/pocs/models.py`:

```python
from django.db import models
from django.conf import settings
from apps.analysis.models import Analysis

class ProofOfConcept(models.Model):
    STATUS_CHOICES = [
        ('requested', 'Requested'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE, related_name='pocs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='requested')
    
    # Configuration
    target_os = models.CharField(max_length=50)
    target_language_version = models.CharField(max_length=50)
    exploitation_goal = models.CharField(max_length=100)
    use_deep_thinking = models.BooleanField(default=False)
    additional_context = models.TextField(blank=True, null=True)
    
    # Results
    code = models.TextField(blank=True, null=True)
    explanation = models.TextField(blank=True, null=True)
    setup_instructions = models.TextField(blank=True, null=True)
    security_warnings = models.TextField(blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completion_time = models.IntegerField(null=True, blank=True, help_text="Time in seconds")
    tokens_used = models.IntegerField(null=True, blank=True)
    
    # Feedback
    user_feedback = models.TextField(blank=True, null=True)
    worked_as_expected = models.BooleanField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Proof of Concept"
        verbose_name_plural = "Proofs of Concept"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"PoC for {self.analysis.advisory.github_id} ({self.get_status_display()})"
    
    @property
    def short_code(self):
        """Return a shortened version of the code for previews"""
        if not self.code:
            return "No code generated"
        lines = self.code.split('\n')
        if len(lines) > 10:
            return '\n'.join(lines[:10]) + '\n...'
        return self.code
```

### Step 2: Set Up the App and Admin Configuration

1. Create the app structure:

```bash
mkdir -p apps/pocs/templates/pocs
mkdir -p apps/pocs/static/pocs/css
mkdir -p apps/pocs/static/pocs/js
touch apps/pocs/__init__.py
touch apps/pocs/admin.py
touch apps/pocs/apps.py
touch apps/pocs/views.py
touch apps/pocs/urls.py
touch apps/pocs/forms.py
```

2. Configure the app in `apps/pocs/apps.py`:

```python
from django.apps import AppConfig

class PocsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.pocs'
    verbose_name = 'Proof of Concept Generation'
```

3. Set up the admin interface in `apps/pocs/admin.py`:

```python
from django.contrib import admin
from .models import ProofOfConcept

@admin.register(ProofOfConcept)
class ProofOfConceptAdmin(admin.ModelAdmin):
    list_display = ('id', 'analysis', 'target_os', 'status', 'user', 'created_at')
    list_filter = ('status', 'target_os', 'use_deep_thinking')
    search_fields = ('analysis__advisory__github_id', 'user__username')
    readonly_fields = ('created_at', 'updated_at', 'completion_time', 'tokens_used')
    fieldsets = (
        ('Relationship', {
            'fields': ('analysis', 'user')
        }),
        ('Status', {
            'fields': ('status', 'created_at', 'updated_at', 'completion_time', 'tokens_used')
        }),
        ('Configuration', {
            'fields': ('target_os', 'target_language_version', 'exploitation_goal', 
                      'use_deep_thinking', 'additional_context')
        }),
        ('Results', {
            'fields': ('code', 'explanation', 'setup_instructions', 'security_warnings')
        }),
        ('Feedback', {
            'fields': ('user_feedback', 'worked_as_expected')
        }),
    )
```

### Step 3: Create the Request Form

Create a form for PoC configuration in `apps/pocs/forms.py`:

```python
from django import forms
from .models import ProofOfConcept

class PoCRequestForm(forms.ModelForm):
    """Form for configuring a new PoC generation request"""
    
    class Meta:
        model = ProofOfConcept
        fields = ['target_os', 'target_language_version', 'exploitation_goal', 
                 'use_deep_thinking', 'additional_context']
        widgets = {
            'target_os': forms.Select(choices=[
                ('Linux', 'Linux'),
                ('Windows', 'Windows'),
                ('macOS', 'macOS'),
                ('Other', 'Other')
            ]),
            'exploitation_goal': forms.Select(choices=[
                ('Demonstrate Vulnerability', 'Demonstrate Vulnerability'),
                ('Remote Code Execution', 'Remote Code Execution'),
                ('Information Disclosure', 'Information Disclosure'),
                ('Privilege Escalation', 'Privilege Escalation'),
                ('Denial of Service', 'Denial of Service')
            ]),
            'additional_context': forms.Textarea(attrs={'rows': 4})
        }
        labels = {
            'target_os': 'Target Operating System',
            'target_language_version': 'Target Language/Framework Version',
            'exploitation_goal': 'Exploitation Goal',
            'use_deep_thinking': 'Use Deep Thinking Mode',
            'additional_context': 'Additional Context'
        }
        help_texts = {
            'target_language_version': 'e.g., Python 3.9, Node.js 16, Java 11',
            'use_deep_thinking': 'Enables more comprehensive reasoning (takes longer)',
            'additional_context': 'Any additional requirements or constraints for the PoC'
        }
```

### Step 4: Create Basic Views

Define the basic views in `apps/pocs/views.py`:

```python
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import reverse
from django.contrib import messages
from .models import ProofOfConcept
from .forms import PoCRequestForm
from apps.analysis.models import Analysis
import time

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
            
            # For Phase 1, we'll simulate the generation process
            # In later phases, we'll implement the actual async generation
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
    
    # For Phase 1, we'll simulate status progression
    # In later phases, this will check the actual status
    if poc.status == 'requested':
        # Simulate processing after a delay
        if (time.time() - poc.created_at.timestamp()) > 5:
            poc.status = 'processing'
            poc.save()
    
    if poc.status == 'processing':
        # Simulate completion after a delay
        if (time.time() - poc.updated_at.timestamp()) > 10:
            poc.status = 'completed'
            poc.completion_time = 15  # Simulated completion time
            poc.code = "print('Hello, PoC!')"
            poc.explanation = "This is a simulated PoC explanation."
            poc.setup_instructions = "These are simulated setup instructions."
            poc.security_warnings = "These are simulated security warnings."
            poc.save()
    
    data = {
        'status': poc.status,
        'created_at': poc.created_at.isoformat(),
        'updated_at': poc.updated_at.isoformat(),
    }
    
    if poc.status == 'completed':
        data['completion_time'] = poc.completion_time
    
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
    """View to handle PoC feedback submission"""
    poc = get_object_or_404(ProofOfConcept, pk=poc_id)
    
    # Ensure user has access
    if poc.user != request.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to submit feedback for this PoC.")
        return redirect('analysis-detail', analysis_id=poc.analysis.id)
    
    if request.method == 'POST':
        worked = request.POST.get('worked_as_expected')
        feedback = request.POST.get('user_feedback')
        
        if worked in ['true', 'false']:
            poc.worked_as_expected = (worked == 'true')
            poc.user_feedback = feedback
            poc.save()
            
            messages.success(request, "Thank you for your feedback!")
        
    return redirect('view_poc', poc_id=poc.id)
```

### Step 5: Set Up URLs

Define the URL patterns in `apps/pocs/urls.py`:

```python
from django.urls import path
from . import views

urlpatterns = [
    path('request/<int:analysis_id>/', views.request_poc, name='request_poc'),
    path('status/<int:poc_id>/', views.poc_status, name='poc_status'),
    path('status/<int:poc_id>/api/', views.poc_status_api, name='poc_status_api'),
    path('view/<int:poc_id>/', views.view_poc, name='view_poc'),
    path('feedback/<int:poc_id>/', views.poc_feedback, name='poc_feedback'),
]
```

### Step 6: Create Templates

1. Create the PoC request form template in `apps/pocs/templates/pocs/request_form.html`:

```html
{% extends "base.html" %}

{% block title %}Configure PoC | ReportGPT Web{% endblock %}

{% block content %}
<div class="row justify-content-center">
    <div class="col-md-10">
        <div class="card">
            <div class="card-header bg-danger text-white">
                <h3 class="mb-0">
                    <i class="fas fa-code"></i> Configure Proof of Concept
                </h3>
            </div>
            <div class="card-body">
                <form method="post">
                    {% csrf_token %}
                    
                    <div class="alert alert-warning">
                        <i class="fas fa-exclamation-triangle"></i>
                        <strong>Important:</strong> Proof of Concept code should be used for testing and verification purposes only. 
                        Use in accordance with your organization's security policies and legal requirements.
                    </div>
                    
                    <div class="row">
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label for="{{ form.target_os.id_for_label }}" class="form-label">{{ form.target_os.label }}</label>
                                {{ form.target_os }}
                                {% if form.target_os.help_text %}
                                <small class="form-text text-muted">{{ form.target_os.help_text }}</small>
                                {% endif %}
                                {% if form.target_os.errors %}
                                <div class="invalid-feedback">{{ form.target_os.errors }}</div>
                                {% endif %}
                            </div>
                        </div>
                        
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label for="{{ form.target_language_version.id_for_label }}" class="form-label">{{ form.target_language_version.label }}</label>
                                {{ form.target_language_version }}
                                {% if form.target_language_version.help_text %}
                                <small class="form-text text-muted">{{ form.target_language_version.help_text }}</small>
                                {% endif %}
                                {% if form.target_language_version.errors %}
                                <div class="invalid-feedback">{{ form.target_language_version.errors }}</div>
                                {% endif %}
                            </div>
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <label for="{{ form.exploitation_goal.id_for_label }}" class="form-label">{{ form.exploitation_goal.label }}</label>
                        {{ form.exploitation_goal }}
                        {% if form.exploitation_goal.help_text %}
                        <small class="form-text text-muted">{{ form.exploitation_goal.help_text }}</small>
                        {% endif %}
                        {% if form.exploitation_goal.errors %}
                        <div class="invalid-feedback">{{ form.exploitation_goal.errors }}</div>
                        {% endif %}
                    </div>
                    
                    <div class="mb-3">
                        <div class="form-check">
                            {{ form.use_deep_thinking }}
                            <label for="{{ form.use_deep_thinking.id_for_label }}" class="form-check-label">
                                {{ form.use_deep_thinking.label }}
                            </label>
                            {% if form.use_deep_thinking.help_text %}
                            <small class="form-text text-muted d-block">{{ form.use_deep_thinking.help_text }}</small>
                            {% endif %}
                            {% if form.use_deep_thinking.errors %}
                            <div class="invalid-feedback">{{ form.use_deep_thinking.errors }}</div>
                            {% endif %}
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <label for="{{ form.additional_context.id_for_label }}" class="form-label">{{ form.additional_context.label }}</label>
                        {{ form.additional_context }}
                        {% if form.additional_context.help_text %}
                        <small class="form-text text-muted">{{ form.additional_context.help_text }}</small>
                        {% endif %}
                        {% if form.additional_context.errors %}
                        <div class="invalid-feedback">{{ form.additional_context.errors }}</div>
                        {% endif %}
                    </div>
                    
                    <div class="text-end">
                        <a href="{% url 'analysis-detail' analysis.id %}" class="btn btn-secondary">Cancel</a>
                        <button type="submit" class="btn btn-danger">
                            <i class="fas fa-code"></i> Generate PoC
                        </button>
                    </div>
                </form>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

2. Create the status page template in `apps/pocs/templates/pocs/status.html`:

```html
{% extends "base.html" %}

{% block title %}PoC Generation Status | ReportGPT Web{% endblock %}

{% block content %}
<div class="row justify-content-center">
    <div class="col-md-10">
        <div class="card">
            <div class="card-header bg-primary text-white">
                <h3 class="mb-0">
                    <i class="fas fa-spinner"></i> PoC Generation Status
                </h3>
            </div>
            <div class="card-body">
                <!-- Status information -->
                <div class="mb-4">
                    <h4>Status: <span id="status-badge" class="badge bg-warning">{{ poc.get_status_display }}</span></h4>
                    <div class="progress mt-3" style="height: 20px;">
                        <div id="progress-bar" class="progress-bar progress-bar-striped progress-bar-animated" 
                             role="progressbar" style="width: 25%;" aria-valuenow="25" aria-valuemin="0" aria-valuemax="100">
                        </div>
                    </div>
                </div>
                
                <!-- Request details -->
                <div class="mb-4">
                    <h5>Request Details</h5>
                    <table class="table">
                        <tr>
                            <th width="30%">Advisory</th>
                            <td>{{ poc.analysis.advisory.github_id }}</td>
                        </tr>
                        <tr>
                            <th>Target OS</th>
                            <td>{{ poc.target_os }}</td>
                        </tr>
                        <tr>
                            <th>Target Language</th>
                            <td>{{ poc.target_language_version }}</td>
                        </tr>
                        <tr>
                            <th>Exploitation Goal</th>
                            <td>{{ poc.exploitation_goal }}</td>
                        </tr>
                        <tr>
                            <th>Deep Thinking Mode</th>
                            <td>{% if poc.use_deep_thinking %}Enabled{% else %}Disabled{% endif %}</td>
                        </tr>
                        <tr>
                            <th>Requested</th>
                            <td>{{ poc.created_at }}</td>
                        </tr>
                    </table>
                </div>
                
                <div class="text-center" id="loading-indicator">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <p class="mt-2">Generating PoC... This may take several minutes.</p>
                </div>
                
                <div class="text-center mt-4" id="completion-actions" style="display: none;">
                    <a href="{% url 'view_poc' poc.id %}" class="btn btn-success">
                        <i class="fas fa-eye"></i> View Generated PoC
                    </a>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script>
    // Status polling function
    function checkStatus() {
        fetch('{% url "poc_status_api" poc.id %}')
            .then(response => response.json())
            .then(data => {
                // Update status badge
                const statusBadge = document.getElementById('status-badge');
                statusBadge.textContent = data.status.charAt(0).toUpperCase() + data.status.slice(1);
                
                // Update progress bar
                const progressBar = document.getElementById('progress-bar');
                
                if (data.status === 'requested') {
                    statusBadge.className = 'badge bg-secondary';
                    progressBar.style.width = '10%';
                } else if (data.status === 'processing') {
                    statusBadge.className = 'badge bg-warning';
                    progressBar.style.width = '50%';
                } else if (data.status === 'completed') {
                    statusBadge.className = 'badge bg-success';
                    progressBar.style.width = '100%';
                    progressBar.classList.remove('progress-bar-animated');
                    
                    // Hide loading indicator
                    document.getElementById('loading-indicator').style.display = 'none';
                    
                    // Show completion actions
                    document.getElementById('completion-actions').style.display = 'block';
                } else if (data.status === 'failed') {
                    statusBadge.className = 'badge bg-danger';
                    progressBar.style.width = '100%';
                    progressBar.classList.remove('progress-bar-animated');
                    progressBar.classList.add('bg-danger');
                    
                    // Hide loading indicator
                    document.getElementById('loading-indicator').style.display = 'none';
                }
                
                // Continue polling if not complete
                if (data.status === 'requested' || data.status === 'processing') {
                    setTimeout(checkStatus, 2000);
                }
            });
    }
    
    // Start polling when page loads
    document.addEventListener('DOMContentLoaded', function() {
        checkStatus();
    });
</script>
{% endblock %}
```

3. Create the basic PoC detail template in `apps/pocs/templates/pocs/detail.html`:

```html
{% extends "base.html" %}
{% load analysis_extras %}

{% block title %}Proof of Concept | ReportGPT Web{% endblock %}

{% block content %}
<div class="row">
    <div class="col-md-8">
        <!-- PoC Code Card -->
        <div class="card mb-4">
            <div class="card-header bg-dark text-white d-flex justify-content-between align-items-center">
                <h3 class="mb-0">
                    <i class="fas fa-code"></i> Proof of Concept Code
                </h3>
                <button class="btn btn-sm btn-outline-light" id="copy-code-btn">
                    <i class="fas fa-copy"></i> Copy
                </button>
            </div>
            <div class="card-body p-0">
                <pre class="rounded-0 mb-0"><code>{{ poc.code }}</code></pre>
            </div>
        </div>
        
        <!-- Setup Instructions -->
        <div class="card mb-4">
            <div class="card-header bg-primary text-white">
                <h3 class="mb-0">
                    <i class="fas fa-cogs"></i> Setup Instructions
                </h3>
            </div>
            <div class="card-body markdown-content">
                {{ poc.setup_instructions|markdown_to_html }}
            </div>
        </div>
        
        <!-- Security Warnings -->
        <div class="card mb-4">
            <div class="card-header bg-danger text-white">
                <h3 class="mb-0">
                    <i class="fas fa-exclamation-triangle"></i> Security Warnings
                </h3>
            </div>
            <div class="card-body markdown-content">
                {{ poc.security_warnings|markdown_to_html }}
                
                <div class="alert alert-warning mt-3">
                    <strong>Disclaimer:</strong> This PoC is provided for security testing and verification purposes only. 
                    Use responsibly and in accordance with applicable laws and regulations.
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-md-4">
        <!-- PoC Info Card -->
        <div class="card mb-4">
            <div class="card-header bg-light">
                <h3 class="mb-0">
                    <i class="fas fa-info-circle"></i> PoC Information
                </h3>
            </div>
            <div class="card-body">
                <table class="table">
                    <tr>
                        <th>Status</th>
                        <td><span class="badge bg-success">{{ poc.get_status_display }}</span></td>
                    </tr>
                    <tr>
                        <th>Advisory</th>
                        <td>
                            <a href="{% url 'advisory-detail' poc.analysis.advisory.github_id %}">
                                {{ poc.analysis.advisory.github_id }}
                            </a>
                        </td>
                    </tr>
                    <tr>
                        <th>Analysis</th>
                        <td>
                            <a href="{% url 'analysis-detail' poc.analysis.id %}">
                                View Analysis
                            </a>
                        </td>
                    </tr>
                    <tr>
                        <th>Target OS</th>
                        <td>{{ poc.target_os }}</td>
                    </tr>
                    <tr>
                        <th>Target Language</th>
                        <td>{{ poc.target_language_version }}</td>
                    </tr>
                    <tr>
                        <th>Generated</th>
                        <td>{{ poc.updated_at }}</td>
                    </tr>
                    {% if poc.completion_time %}
                    <tr>
                        <th>Generation Time</th>
                        <td>{{ poc.completion_time }} seconds</td>
                    </tr>
                    {% endif %}
                </table>
            </div>
        </div>
        
        <!-- Explanation Card -->
        <div class="card mb-4">
            <div class="card-header bg-info text-white">
                <h3 class="mb-0">
                    <i class="fas fa-lightbulb"></i> Explanation
                </h3>
            </div>
            <div class="card-body markdown-content">
                {{ poc.explanation|markdown_to_html }}
            </div>
        </div>
        
        <!-- Feedback Card -->
        <div class="card">
            <div class="card-header bg-secondary text-white">
                <h3 class="mb-0">
                    <i class="fas fa-comment"></i> Feedback
                </h3>
            </div>
            <div class="card-body">
                <form method="post" action="{% url 'poc_feedback' poc.id %}">
                    {% csrf_token %}
                    
                    <div class="mb-3">
                        <label class="form-label">Did this PoC work as expected?</label>
                        <div class="form-check">
                            <input class="form-check-input" type="radio" name="worked_as_expected" value="true" id="worked_yes" {% if poc.worked_as_expected == True %}checked{% endif %}>
                            <label class="form-check-label" for="worked_yes">Yes</label>
                        </div>
                        <div class="form-check">
                            <input class="form-check-input" type="radio" name="worked_as_expected" value="false" id="worked_no" {% if poc.worked_as_expected == False %}checked{% endif %}>
                            <label class="form-check-label" for="worked_no">No</label>
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <label for="feedback" class="form-label">Additional Feedback</label>
                        <textarea class="form-control" id="feedback" name="user_feedback" rows="3">{{ poc.user_feedback }}</textarea>
                    </div>
                    
                    <button type="submit" class="btn btn-primary">Submit Feedback</button>
                </form>
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script>
    document.addEventListener('DOMContentLoaded', () => {
        // Code copy functionality
        const copyCodeBtn = document.getElementById('copy-code-btn');
        if (copyCodeBtn) {
            copyCodeBtn.addEventListener('click', () => {
                const codeBlock = document.querySelector('pre code');
                const textArea = document.createElement('textarea');
                textArea.value = codeBlock.textContent;
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
                
                // Provide feedback
                copyCodeBtn.innerHTML = '<i class="fas fa-check"></i> Copied';
                setTimeout(() => {
                    copyCodeBtn.innerHTML = '<i class="fas fa-copy"></i> Copy';
                }, 2000);
            });
        }
    });
</script>
{% endblock %}
```

### Step 7: Update Analysis Detail Template

Add a "Generate PoC" button to the analysis detail page in `templates/analysis/analysis_detail.html`:

```html
<!-- Add this to the bottom of the page, perhaps after the analysis results section -->
{% if analysis.poc_feasibility >= 5 %}
<div class="card mt-4">
    <div class="card-header bg-danger text-white">
        <h5 class="mb-0">
            <i class="fas fa-code"></i> Proof of Concept
        </h5>
    </div>
    <div class="card-body">
        <p>
            Based on the analysis, this vulnerability has a PoC feasibility score of <strong>{{ analysis.poc_feasibility }}/10</strong>, 
            indicating that a working proof of concept exploit is likely feasible.
        </p>
        
        <div class="text-center">
            <a href="{% url 'request_poc' analysis.id %}" class="btn btn-danger">
                <i class="fas fa-code"></i> Generate Proof of Concept
            </a>
        </div>
    </div>
</div>
{% endif %}
```

### Step 8: Update Project URLs

Add the PoC URLs to the main project's URL configuration in `reportgpt_web/urls.py`:

```python
# Add to the urlpatterns list:
path('pocs/', include('apps.pocs.urls')),
```

### Step 9: Run Migrations

Create and apply migrations for the new model:

```bash
python manage.py makemigrations
python manage.py migrate
```

### Step 10: Test the Basic Flow

At this point, you can test the basic flow with simulated PoC generation:

1. View an analysis with a feasibility score ≥ 5
2. Click "Generate Proof of Concept"
3. Fill in and submit the configuration form
4. Watch the status page for simulated progress
5. View the simulated PoC results
6. Submit feedback

This completes Phase 1, providing the foundation for the PoC Generation System.

## Next Steps

With Phase 1 complete, the next steps would be:

1. Phase 2: Implement the Prompt Engineering System and Generation Service
2. Phase 3: Create more advanced UI components and interactive features
3. Phase 4: Add deep thinking mode and feedback-based improvements