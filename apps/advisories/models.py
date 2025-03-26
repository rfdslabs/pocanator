from django.db import models
from django.urls import reverse
from django.utils import timezone


class Advisory(models.Model):
    """Model representing a GitHub Security Advisory"""
    
    SEVERITY_CHOICES = [
        ('Critical', 'Critical'),
        ('High', 'High'),
        ('Moderate', 'Moderate'),
        ('Low', 'Low'),
        ('Unknown', 'Unknown'),
    ]
    
    github_id = models.CharField(max_length=255, unique=True, help_text="GitHub Advisory ID (e.g., GHSA-xxxx-xxxx-xxxx)")
    url = models.URLField(help_text="URL to the GitHub Advisory")
    title = models.CharField(max_length=255, help_text="Advisory title")
    description = models.TextField(help_text="Full description of the advisory")
    severity = models.CharField(max_length=50, choices=SEVERITY_CHOICES, help_text="Severity level")
    cve_id = models.CharField(max_length=50, blank=True, null=True, help_text="CVE ID if available")
    cvss_score = models.CharField(max_length=10, blank=True, null=True, help_text="CVSS score if available")
    affected_versions = models.TextField(blank=True, null=True, help_text="Affected software versions")
    vulnerability_type = models.CharField(max_length=50, blank=True, null=True, help_text="Type of vulnerability (e.g., RCE, XSS)")
    published_date = models.DateTimeField(blank=True, null=True, help_text="When the advisory was published")
    discovered_date = models.DateTimeField(auto_now_add=True, help_text="When this advisory was discovered by the system")
    
    class Meta:
        verbose_name = "Advisory"
        verbose_name_plural = "Advisories"
        ordering = ['-discovered_date']
    
    def __str__(self):
        return f"{self.github_id}: {self.title}"
    
    def get_absolute_url(self):
        return reverse('advisory-detail', args=[self.github_id])
    
    @property
    def has_analysis(self):
        return self.analyses.exists()
    
    @property
    def has_commits(self):
        return self.commits.exists()
    
    @property
    def severity_class(self):
        """Return CSS class based on severity"""
        severity_classes = {
            'Critical': 'danger',
            'High': 'warning',
            'Moderate': 'info',
            'Low': 'success',
            'Unknown': 'secondary',
        }
        return severity_classes.get(self.severity, 'secondary')


class Commit(models.Model):
    """Model representing a commit associated with an advisory"""
    
    advisory = models.ForeignKey(Advisory, on_delete=models.CASCADE, related_name='commits')
    repo_name = models.CharField(max_length=255, help_text="Repository name (e.g., owner/repo)")
    commit_hash = models.CharField(max_length=40, help_text="Full commit hash")
    commit_url = models.URLField(help_text="URL to the commit on GitHub")
    diff_text = models.TextField(help_text="Raw diff text")
    lines_added = models.IntegerField(default=0, help_text="Number of lines added")
    lines_removed = models.IntegerField(default=0, help_text="Number of lines removed")
    fetch_date = models.DateTimeField(auto_now_add=True, help_text="When this commit was fetched")
    
    class Meta:
        verbose_name = "Commit"
        verbose_name_plural = "Commits"
        ordering = ['fetch_date']
        unique_together = ['advisory', 'commit_hash']
    
    def __str__(self):
        return f"{self.repo_name}@{self.commit_hash[:7]}"
    
    @property
    def short_hash(self):
        return self.commit_hash[:7]
    
    @property
    def files_changed(self):
        """Count files changed based on diff text"""
        if not self.diff_text:
            return 0
        return self.diff_text.count('diff --git')