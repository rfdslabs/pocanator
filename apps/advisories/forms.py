from django import forms
import re


class ImportAdvisoryForm(forms.Form):
    """Form for importing an advisory from GitHub"""
    
    advisory_url = forms.URLField(
        label="GitHub Advisory URL or ID",
        help_text="Enter a GitHub Advisory URL (https://github.com/advisories/GHSA-xxxx-xxxx-xxxx) or just the ID.",
        widget=forms.TextInput(attrs={
            'placeholder': 'GHSA-xxxx-xxxx-xxxx or full URL',
            'class': 'form-control'
        })
    )
    
    def clean_advisory_url(self):
        """Validate and normalize the advisory URL or ID"""
        value = self.cleaned_data['advisory_url']
        
        # If it's just the GHSA ID, convert to URL
        if re.match(r'^GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}$', value):
            return f"https://github.com/advisories/{value}"
        
        # If it's a URL, make sure it's a GitHub advisory URL
        if not re.search(r'github\.com/advisories/GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}', value):
            raise forms.ValidationError(
                "Please enter a valid GitHub Advisory URL or ID (GHSA-xxxx-xxxx-xxxx)"
            )
        
        return value