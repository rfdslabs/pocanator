from django.db import models
from django.urls import reverse
from django.conf import settings
from apps.advisories.models import Advisory


class Analysis(models.Model):
    """Model representing a vulnerability analysis"""
    
    COMPLEXITY_CHOICES = [
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
    ]
    
    advisory = models.ForeignKey(Advisory, on_delete=models.CASCADE, related_name='analyses')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                             null=True, blank=True, related_name='analyses')
    
    # Analysis metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    model_used = models.CharField(max_length=100, default="gpt-4o",
                                  help_text="AI model used for analysis")
    provider = models.CharField(max_length=30, blank=True, default="",
                                help_text="LLM provider that produced this analysis")
    fingerprint = models.CharField(max_length=64, blank=True, default="", db_index=True,
                                   help_text="Content hash of (prompt version, provider, "
                                             "model, advisory+patch) for result reuse")
    
    # Basic classification
    vuln_type = models.CharField(max_length=50, help_text="Type of vulnerability (e.g., RCE, XSS)")
    severity = models.CharField(max_length=50, blank=True, null=True,
                                help_text="Severity as assessed by the model")
    cwe = models.CharField(max_length=50, blank=True, null=True,
                           help_text="CWE identifier (e.g. CWE-89)")
    
    # Detailed analysis
    vuln_explanation = models.TextField(help_text="Explanation of the vulnerability")
    patch_analysis = models.TextField(help_text="Analysis of how the patch addresses the vulnerability")
    impact_summary = models.TextField(help_text="Summary of potential impact if exploited")
    
    # Metrics
    patch_effectiveness = models.IntegerField(help_text="Effectiveness rating of patch (0-10)")
    poc_feasibility = models.IntegerField(help_text="Feasibility of creating a PoC (0-10)")
    poc_complexity = models.CharField(max_length=50, choices=COMPLEXITY_CHOICES,
                                     help_text="Complexity of creating a PoC")
    confidence = models.IntegerField(default=0,
                                     help_text="Model's confidence in this analysis (0-10)")
    tokens_used = models.IntegerField(default=0, help_text="Total tokens used for this analysis")
    estimated_cost = models.FloatField(default=0.0, help_text="Estimated API cost in USD")
    
    # Additional details
    required_skills = models.TextField(blank=True, null=True, 
                                     help_text="Skills required for exploitation")
    information_gaps = models.TextField(blank=True, null=True,
                                       help_text="Information gaps that would need to be filled")
    key_indicators = models.TextField(blank=True, null=True,
                                     help_text="Key vulnerability indicators")
    
    # Reports
    markdown_report = models.TextField(blank=True, null=True, 
                                      help_text="Full markdown report")
    html_report = models.TextField(blank=True, null=True,
                                  help_text="Full HTML report")
    
    class Meta:
        verbose_name = "Analysis"
        verbose_name_plural = "Analyses"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Analysis for {self.advisory.github_id}"
    
    def get_absolute_url(self):
        return reverse('analysis-detail', args=[self.pk])
    
    @property
    def poc_feasibility_class(self):
        """Return CSS class based on PoC feasibility score"""
        if self.poc_feasibility >= 8:
            return 'danger'
        elif self.poc_feasibility >= 5:
            return 'warning'
        elif self.poc_feasibility >= 3:
            return 'info'
        else:
            return 'success'
    
    @property
    def patch_effectiveness_class(self):
        """Return CSS class based on patch effectiveness score"""
        if self.patch_effectiveness >= 8:
            return 'success'
        elif self.patch_effectiveness >= 5:
            return 'info'
        elif self.patch_effectiveness >= 3:
            return 'warning'
        else:
            return 'danger'
            
    @property
    def result_summary(self):
        """Return a summary of the analysis for display in lists"""
        if self.vuln_explanation:
            return self.vuln_explanation
        elif self.markdown_report:
            # Try to extract a summary from the markdown report
            import re
            # Look for vulnerability explanation section
            vuln_expl = re.search(r'## [^#]*Vulnerability Explanation[^#]*\n(.*?)(?=##|\Z)', 
                                self.markdown_report, re.DOTALL)
            if vuln_expl:
                return vuln_expl.group(1).strip()
            # Fallback to the first 200 chars
            return self.markdown_report[:200] + '...'
        return "No summary available"