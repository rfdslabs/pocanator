from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
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
    language = models.CharField(max_length=50, blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completion_time = models.IntegerField(null=True, blank=True, help_text="Time in seconds")
    tokens_used = models.IntegerField(null=True, blank=True)
    
    # Feedback
    user_feedback = models.TextField(blank=True, null=True)
    worked_as_expected = models.BooleanField(null=True, blank=True)
    effectiveness_score = models.IntegerField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="User rating of PoC effectiveness (1-10)"
    )
    feedback_categories = models.JSONField(
        null=True,
        blank=True,
        help_text="Categories of feedback (e.g., 'env_setup', 'accuracy', 'clarity')"
    )
    
    # Template tracking
    template_used = models.ForeignKey(
        'PoCTemplate', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='generated_pocs'
    )
    
    # History tracking
    previous_version = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='next_versions',
        help_text="Previous version of this PoC (for regeneration history)"
    )
    
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


class PoCTemplate(models.Model):
    """
    Templates for different vulnerability types to guide PoC generation.
    These are learned from successful PoCsand used to improve future generations.
    """
    VULNERABILITY_TYPE_CHOICES = [
        ('RCE', 'Remote Code Execution'),
        ('XSS', 'Cross-Site Scripting'),
        ('SQLI', 'SQL Injection'),
        ('SSRF', 'Server-Side Request Forgery'),
        ('PATH_TRAVERSAL', 'Path Traversal'),
        ('DESERIALIZATION', 'Deserialization'),
        ('COMMAND_INJECTION', 'Command Injection'),
        ('FILE_UPLOAD', 'Unrestricted File Upload'),
        ('IDOR', 'Insecure Direct Object Reference'),
        ('DEFAULT', 'Generic Vulnerability')
    ]
    
    vulnerability_type = models.CharField(max_length=50, choices=VULNERABILITY_TYPE_CHOICES)
    name = models.CharField(max_length=100)
    description = models.TextField()
    system_prompt = models.TextField(help_text="System prompt for the LLM")
    user_prompt_template = models.TextField(help_text="Template for user prompt with placeholders")
    code_skeleton = models.TextField(null=True, blank=True, help_text="Optional code structure to start from")
    
    # Performance metrics
    usage_count = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    average_effectiveness = models.FloatField(default=0.0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "PoC Template"
        verbose_name_plural = "PoC Templates"
        ordering = ['-average_effectiveness', '-usage_count']
    
    def __str__(self):
        return f"{self.name} ({self.vulnerability_type})"
    
    @property
    def success_rate(self):
        """Calculate the success rate percentage"""
        if self.usage_count == 0:
            return 0
        return (self.success_count / self.usage_count) * 100
    
    def update_metrics(self, effectiveness_score, worked):
        """Update the template's performance metrics based on a new PoC"""
        self.usage_count += 1
        
        if worked:
            self.success_count += 1
        
        # Update the average effectiveness if score provided
        if effectiveness_score is not None:
            if self.average_effectiveness == 0:
                self.average_effectiveness = effectiveness_score
            else:
                # Moving average calculation
                self.average_effectiveness = (
                    (self.average_effectiveness * (self.usage_count - 1)) + effectiveness_score
                ) / self.usage_count
        
        self.save()


class PoCFeedbackAnalysis(models.Model):
    """
    Analysis of feedback patterns to improve PoC generation.
    This model stores aggregated insights from user feedback.
    """
    vulnerability_type = models.CharField(max_length=50)
    feedback_category = models.CharField(max_length=50)
    common_issues = models.TextField()
    suggested_improvements = models.TextField()
    affected_prompt_sections = models.JSONField(default=list)
    
    # Metadata
    sample_size = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)
    confidence_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    
    class Meta:
        verbose_name = "PoC Feedback Analysis"
        verbose_name_plural = "PoC Feedback Analyses"
        unique_together = ('vulnerability_type', 'feedback_category')
    
    def __str__(self):
        return f"{self.vulnerability_type} - {self.feedback_category} Feedback Analysis"