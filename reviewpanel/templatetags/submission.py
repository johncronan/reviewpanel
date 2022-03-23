from django import template


register = template.Library()

@register.simple_tag(takes_context=True)
def dereference(context, ref, submission):
    block_name = ref.name if not ref.collection else ref.collection
    block = context['blocks'][block_name]
    
    if block.block_type() == 'custom': return getattr(submission, block_name)
    elif block.block_type() == 'stock':
        stock = block.stock
        values = { n: getattr(submission, stock.field_name(n))
                   for n in stock.widget_names() }
        return stock.render(ref.field, **values)
    else:
        pass #TODO
