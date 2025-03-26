# PoC Generation System: User Interface

## Overview

The User Interface component of the PoC Generation System provides intuitive interfaces for requesting, configuring, and reviewing proof-of-concept exploits. It ensures a seamless user experience throughout the PoC generation workflow.

## Key Interface Components

### 1. PoC Request Button

A prominent "Generate PoC" button is displayed on the Analysis Detail page when the PoC feasibility score exceeds a certain threshold (typically 5/10).

```html
<!-- In analysis_detail.html -->
{% if analysis.poc_feasibility >= 5 %}
<div class="mt-4">
    <a href="{% url 'request_poc' analysis.id %}" class="btn btn-danger">
        <i class="fas fa-code"></i> Generate Proof of Concept
    </a>
    <small class="text-muted d-block mt-2">
        <i class="fas fa-info-circle"></i> PoC feasibility score: {{ analysis.poc_feasibility }}/10
    </small>
</div>
{% endif %}
```

### 2. PoC Configuration Form

A form for configuring the PoC generation parameters.

```html
<!-- In poc_request_form.html -->
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
                        <label for="id_target_os" class="form-label">Target Operating System</label>
                        <select name="target_os" id="id_target_os" class="form-select">
                            <option value="Linux">Linux</option>
                            <option value="Windows">Windows</option>
                            <option value="macOS">macOS</option>
                            <option value="Other">Other</option>
                        </select>
                    </div>
                </div>
                
                <div class="col-md-6">
                    <div class="mb-3">
                        <label for="id_target_language_version" class="form-label">Target Language/Framework Version</label>
                        <input type="text" name="target_language_version" id="id_target_language_version" class="form-control"
                               placeholder="e.g., Python 3.9, Node.js 16">
                    </div>
                </div>
            </div>
            
            <div class="mb-3">
                <label for="id_exploitation_goal" class="form-label">Exploitation Goal</label>
                <select name="exploitation_goal" id="id_exploitation_goal" class="form-select">
                    <option value="Demonstrate Vulnerability">Demonstrate Vulnerability</option>
                    <option value="Remote Code Execution">Remote Code Execution</option>
                    <option value="Information Disclosure">Information Disclosure</option>
                    <option value="Privilege Escalation">Privilege Escalation</option>
                    <option value="Denial of Service">Denial of Service</option>
                </select>
            </div>
            
            <div class="mb-3">
                <div class="form-check">
                    <input type="checkbox" name="use_deep_thinking" id="id_use_deep_thinking" class="form-check-input">
                    <label for="id_use_deep_thinking" class="form-check-label">
                        Use Deep Thinking Mode
                    </label>
                    <small class="form-text text-muted d-block">
                        This mode uses more advanced reasoning but takes longer to generate results.
                    </small>
                </div>
            </div>
            
            <div class="mb-3">
                <label for="id_additional_context" class="form-label">Additional Context</label>
                <textarea name="additional_context" id="id_additional_context" class="form-control" rows="4"
                          placeholder="Any additional information or requirements for the PoC..."></textarea>
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
```

### 3. PoC Status Page

A page displaying the current status of the PoC generation process.

```html
<!-- In poc_status.html -->
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
                    setTimeout(checkStatus, 5000);
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

### 4. PoC Detail View

A comprehensive view of the generated PoC with details and explanations.

```html
<!-- In poc_detail.html -->
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
                <pre class="rounded-0 mb-0"><code class="language-{{ poc|get_code_language }}">{{ poc.code }}</code></pre>
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
                    <tr>
                        <th>Generation Time</th>
                        <td>{{ poc.completion_time }} seconds</td>
                    </tr>
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
                            <input class="form-check-input" type="radio" name="worked_as_expected" value="true" id="worked_yes">
                            <label class="form-check-label" for="worked_yes">Yes</label>
                        </div>
                        <div class="form-check">
                            <input class="form-check-input" type="radio" name="worked_as_expected" value="false" id="worked_no">
                            <label class="form-check-label" for="worked_no">No</label>
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <label for="feedback" class="form-label">Additional Feedback</label>
                        <textarea class="form-control" id="feedback" name="user_feedback" rows="3"></textarea>
                    </div>
                    
                    <button type="submit" class="btn btn-primary">Submit Feedback</button>
                </form>
            </div>
        </div>
    </div>
</div>
```

## JavaScript Functionality

### Code Highlighting

```javascript
// In poc_detail.js
document.addEventListener('DOMContentLoaded', () => {
    // Initialize code highlighting
    document.querySelectorAll('pre code').forEach((block) => {
        hljs.highlightBlock(block);
    });
    
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
```

### Status Polling

```javascript
// Status polling function with progress animation
function checkStatus() {
    fetch('{% url "poc_status_api" poc.id %}')
        .then(response => response.json())
        .then(data => {
            // Update UI based on status
            // Calculate progress based on elapsed time and status
            // ...
        });
}
```

## Custom Template Filters

```python
@register.filter
def get_code_language(poc):
    """Determine the code language for syntax highlighting"""
    # Try to detect language from the code
    code = poc.code
    
    if not code:
        return "plaintext"
    
    # Check for common language indicators
    if code.startswith("#!/bin/bash") or "bash" in code.lower()[:50]:
        return "bash"
    elif code.startswith("#!/usr/bin/env python") or "import" in code and "def" in code:
        return "python"
    elif "<?php" in code[:50]:
        return "php"
    elif "function" in code and "var" in code or "const" in code or "let" in code:
        return "javascript"
    elif "public class" in code or "import java" in code:
        return "java"
    elif "#include" in code and ("{" in code or ";" in code):
        return "cpp"
    elif "using namespace" in code or "std::" in code:
        return "cpp"
    elif "<html" in code.lower() or "<!doctype" in code.lower():
        return "html"
    
    # Default to plaintext if we can't determine
    return "plaintext"
```

## Mobile Responsiveness

The UI is designed to be fully responsive, with specific optimizations for mobile devices:

```css
/* Mobile optimizations */
@media (max-width: 768px) {
    .card-header h3 {
        font-size: 1.2rem;
    }
    
    pre {
        max-height: 300px;
    }
    
    .col-md-4 {
        margin-top: 1.5rem;
    }
}
```

## Accessibility Features

The interface includes several accessibility enhancements:

1. Proper ARIA attributes for dynamic content
2. Semantic HTML structure
3. Color contrast compliance
4. Keyboard navigation support
5. Screen reader compatibility

```html
<!-- Example of accessibility-enhanced elements -->
<button aria-label="Copy code to clipboard" class="btn btn-sm btn-outline-light" id="copy-code-btn">
    <i class="fas fa-copy" aria-hidden="true"></i> Copy
</button>

<div role="alert" aria-live="polite" id="copy-feedback" class="sr-only">
    Code copied to clipboard
</div>
```

## Future UI Enhancements

1. **Tabbed Interface**: Organize the PoC details into tabbed sections for better information hierarchy
2. **Interactive Testing**: Add controls for testing the PoC in a sandboxed environment
3. **Version History**: Track and display multiple versions of generated PoCs
4. **Collaborative Features**: Allow multiple users to comment and collaborate on PoCs
5. **Visualization Tools**: Add diagrams and visualizations to explain exploit mechanics