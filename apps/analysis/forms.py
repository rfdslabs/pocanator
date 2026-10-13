from django import forms


class CreateAnalysisForm(forms.Form):
    """Form for creating a new analysis"""
    
    MODEL_CHOICES = [
        ('gpt-4o', 'GPT-4o (Recommended)'),
        ('gpt-4-turbo', 'GPT-4 Turbo'),
        ('gpt-3.5-turbo', 'GPT-3.5 Turbo (Faster, less accurate)'),
    ]
    
    model = forms.ChoiceField(
        choices=MODEL_CHOICES,
        initial='gpt-4o',
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Select the AI model to use for analysis.'
    )