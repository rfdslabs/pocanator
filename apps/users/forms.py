from django import forms
from .models import UserProfile


class UserProfileForm(forms.ModelForm):
    """Form for editing user profile"""
    
    class Meta:
        model = UserProfile
        fields = ['openai_api_key', 'github_token', 'default_model']
        widgets = {
            'openai_api_key': forms.PasswordInput(render_value=True, attrs={'class': 'form-control'}),
            'github_token': forms.PasswordInput(render_value=True, attrs={'class': 'form-control'}),
            'default_model': forms.Select(attrs={'class': 'form-select'})
        }
        help_texts = {
            'openai_api_key': 'Your personal OpenAI API key (optional).',
            'github_token': 'Your personal GitHub token for API access (optional).',
            'default_model': 'Default AI model to use for analysis.'
        }


class APIKeyForm(forms.Form):
    """Form for managing API keys"""
    
    regenerate_key = forms.BooleanField(
        required=False,
        label='Regenerate API Key',
        help_text='Check this box to regenerate your API key. Warning: This will invalidate your existing key!'
    )