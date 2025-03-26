"""
Template tags and filters for the PoC app
"""
from django import template

register = template.Library()

@register.filter
def calculate_cost(tokens):
    """
    Calculate the approximate cost of the API call.
    
    Args:
        tokens: Number of tokens used
        
    Returns:
        Estimated cost in USD
    """
    if not tokens:
        return 0
    
    # Base pricing as of 2024 for GPT-4o
    # $10 per million tokens for input
    # $30 per million tokens for output
    
    # Estimate 75% of tokens are input and 25% are output for a typical PoC generation
    input_tokens = int(tokens * 0.75)
    output_tokens = tokens - input_tokens
    
    input_cost = (input_tokens / 1000000) * 10
    output_cost = (output_tokens / 1000000) * 30
    
    return input_cost + output_cost