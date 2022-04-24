from django import template


register = template.Library()

@register.filter
def items(val): # dict.items in template won't work when 'items' is a key
    return val.items()
