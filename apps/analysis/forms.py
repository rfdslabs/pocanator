from django import forms

from .providers import DEFAULT_MODEL, grouped_choices


class CreateAnalysisForm(forms.Form):
    """Form for creating a new analysis"""

    model = forms.ChoiceField(
        choices=grouped_choices,
        initial=DEFAULT_MODEL,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Select the AI model to use for analysis. The provider is '
                  'chosen automatically from the model.',
    )
