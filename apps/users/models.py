from django.db import models
from django.conf import settings
from django.utils.crypto import get_random_string


class UserProfile(models.Model):
    """Extended user profile with additional settings and preferences"""
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    api_key = models.CharField(max_length=64, blank=True, null=True, unique=True, 
                              help_text="API key for programmatic access")
    openai_api_key = models.CharField(max_length=255, blank=True, null=True,
                                    help_text="Personal OpenAI API key")
    github_token = models.CharField(max_length=255, blank=True, null=True,
                                  help_text="Personal GitHub token")
    default_model = models.CharField(max_length=50, default="gpt-4o",
                                    help_text="Default AI model to use")
    
    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"
    
    def __str__(self):
        return f"Profile for {self.user.username}"
    
    def save(self, *args, **kwargs):
        if not self.api_key:
            self.api_key = self.generate_api_key()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_api_key():
        """Generate a random API key"""
        return get_random_string(length=32)
    
    @property
    def has_custom_openai_key(self):
        return bool(self.openai_api_key)
    
    @property
    def has_github_token(self):
        return bool(self.github_token)


class APIUsage(models.Model):
    """Tracks API usage for billing and rate limiting"""
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_usage')
    timestamp = models.DateTimeField(auto_now_add=True)
    endpoint = models.CharField(max_length=255, help_text="API endpoint used")
    tokens_used = models.IntegerField(default=0, help_text="Number of tokens used")
    model = models.CharField(max_length=50, help_text="AI model used")
    cost = models.DecimalField(max_digits=10, decimal_places=6, default=0,
                             help_text="Cost in USD")
    
    class Meta:
        verbose_name = "API Usage"
        verbose_name_plural = "API Usage"
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.user.username} - {self.endpoint} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"