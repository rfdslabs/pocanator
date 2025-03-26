from django import template
from django.db.models import Sum

register = template.Library()

@register.filter
def map(obj_list, attribute):
    """
    Return an iterable of values by mapping an attribute on an iterable of objects.
    
    Example:
        {{ mylist|map:"attribute" }}
    """
    if not obj_list:
        return []
    return [getattr(obj, attribute, 0) for obj in obj_list]

@register.filter
def sum_values(value_list):
    """
    Return the sum of a list of values.
    
    Example:
        {{ mylist|sum_values }}
    """
    if not value_list:
        return 0
    return sum(value_list)