from django import forms
from .models import ProofOfConcept

class PoCRequestForm(forms.ModelForm):
    """Form for configuring a new PoC generation request"""
    
    class Meta:
        model = ProofOfConcept
        fields = ['target_os', 'target_language_version', 'exploitation_goal', 
                 'use_deep_thinking', 'additional_context']
        widgets = {
            'target_os': forms.Select(choices=[
                ('Linux', 'Linux'),
                ('Windows', 'Windows'),
                ('macOS', 'macOS'),
                ('Other', 'Other')
            ]),
            'exploitation_goal': forms.Select(choices=[
                ('Demonstrate Vulnerability', 'Demonstrate Vulnerability'),
                ('Remote Code Execution', 'Remote Code Execution'),
                ('Information Disclosure', 'Information Disclosure'),
                ('Privilege Escalation', 'Privilege Escalation'),
                ('Denial of Service', 'Denial of Service')
            ]),
            'additional_context': forms.Textarea(attrs={'rows': 4})
        }
        labels = {
            'target_os': 'Target Operating System',
            'target_language_version': 'Target Language/Framework Version',
            'exploitation_goal': 'Exploitation Goal',
            'use_deep_thinking': 'Use Deep Thinking Mode',
            'additional_context': 'Additional Context'
        }
        help_texts = {
            'target_language_version': 'e.g., Python 3.9, Node.js 16, Java 11',
            'use_deep_thinking': 'Enables more comprehensive reasoning (takes longer)',
            'additional_context': 'Any additional requirements or constraints for the PoC'
        }