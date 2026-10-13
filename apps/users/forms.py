from django import forms

from apps.analysis.providers import grouped_choices
from .models import UserProfile


class UserProfileForm(forms.ModelForm):
    """Form for editing user profile"""

    default_model = forms.ChoiceField(
        choices=grouped_choices,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Default AI model to use for analysis.',
    )

    class Meta:
        model = UserProfile
        fields = ['openai_api_key', 'anthropic_api_key', 'github_token', 'default_model']
        widgets = {
            'openai_api_key': forms.PasswordInput(render_value=True, attrs={'class': 'form-control'}),
            'anthropic_api_key': forms.PasswordInput(render_value=True, attrs={'class': 'form-control'}),
            'github_token': forms.PasswordInput(render_value=True, attrs={'class': 'form-control'}),
        }
        help_texts = {
            'openai_api_key': 'Your personal OpenAI API key (optional).',
            'anthropic_api_key': 'Your personal Anthropic (Claude) API key (optional).',
            'github_token': 'Your personal GitHub token for API access (optional).',
        }


class APIKeyForm(forms.Form):
    """Form for managing API keys"""

    regenerate_key = forms.BooleanField(
        required=False,
        label='Regenerate API Key',
        help_text='Check this box to regenerate your API key. Warning: This will invalidate your existing key!'
    )
