# PoC Generation System: Data Models

## ProofOfConcept Model

The `ProofOfConcept` model is the core data structure for the PoC generation system. It tracks all aspects of a PoC request, including configuration, generation parameters, results, and user feedback.

```python
class ProofOfConcept(models.Model):
    STATUS_CHOICES = [
        ('requested', 'Requested'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE, related_name='pocs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
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
```

### Field Descriptions

#### Relationships
- `analysis`: Links to the vulnerability analysis this PoC is based on
- `user`: The user who requested the PoC generation

#### Status Tracking
- `status`: Current stage in the PoC generation workflow
- `created_at`: Timestamp of when the request was created
- `updated_at`: Last update timestamp
- `completion_time`: Time taken to generate the PoC (in seconds)
- `tokens_used`: Number of tokens used for generation (for cost tracking)

#### Configuration Parameters
- `target_os`: Target operating system (e.g., "Linux", "Windows", "macOS")
- `target_language_version`: Version of the target language or framework (e.g., "Python 3.9", "Node.js 16")
- `exploitation_goal`: Purpose of the PoC (e.g., "Remote Code Execution", "Information Disclosure")
- `use_deep_thinking`: Whether to use an enhanced generation approach with deeper reasoning
- `additional_context`: Any extra information provided by the user

#### Generation Results
- `code`: The actual PoC code generated
- `explanation`: Detailed explanation of how the PoC works
- `setup_instructions`: Steps needed to set up and execute the PoC
- `security_warnings`: Safety precautions and containment advice

#### Feedback Data
- `user_feedback`: Textual feedback from the user about the PoC
- `worked_as_expected`: Boolean indicating if the PoC successfully demonstrated the vulnerability

## Related Models

### PoCTemplate (Future Enhancement)

```python
class PoCTemplate(models.Model):
    """Templates for different vulnerability types to guide PoC generation"""
    vulnerability_type = models.CharField(max_length=100)
    template_name = models.CharField(max_length=100)
    prompt_template = models.TextField()
    code_skeleton = models.TextField(null=True, blank=True)
    usage_count = models.IntegerField(default=0)
    success_rate = models.FloatField(default=0.0)
```

### PoCExecution (Future Enhancement)

```python
class PoCExecution(models.Model):
    """Tracks execution attempts of PoCs in sandboxed environments"""
    proof_of_concept = models.ForeignKey(ProofOfConcept, on_delete=models.CASCADE, related_name='executions')
    execution_environment = models.CharField(max_length=100)
    execution_start = models.DateTimeField(auto_now_add=True)
    execution_end = models.DateTimeField(null=True, blank=True)
    result = models.TextField(null=True, blank=True)
    success = models.BooleanField(null=True, blank=True)
    logs = models.TextField(null=True, blank=True)
```