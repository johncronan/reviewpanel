from django.db import models
from django.db.models import UniqueConstraint

from formative import models as f_models


class Template(models.Model):
    class Meta:
        constraints = [
            UniqueConstraint(fields=['program', 'name'],
                             name='unique_program_slug')
        ]
    
    program = models.ForeignKey(f_models.Program, models.CASCADE,
                                related_name='programs',
                                related_query_name='program')
    name = models.SlugField(max_length=32, allow_unicode=True,
                            verbose_name='identifier')
    max_width = models.PositiveIntegerField(default=0)
    
    def __str__(self):
        return self.name


class TemplateSection(models.Model):
    class Meta:
        constraints = [
            UniqueConstraint(fields=['template', 'name'],
                             name='unique_template_name')
        ]
    
    template = models.ForeignKey(Template, models.CASCADE,
                                 related_name='sections',
                                 related_query_name='section')
    name = models.SlugField(max_length=32, allow_unicode=32,
                            verbose_name='identifier')
    x = models.DecimalField(max_digits=7, decimal_places=3, default='0.000',
                            verbose_name='left %')
    y = models.DecimalField(max_digits=7, decimal_places=3, default='0.000',
                            verbose_name='top %')
    w = models.DecimalField(max_digits=7, decimal_places=3, default='100.000',
                            verbose_name='width %')
    h = models.DecimalField(max_digits=7, decimal_places=3,
                            null=True, blank=True, verbose_name='height')
    wrap = models.BooleanField(default=True)
    scroll = models.BooleanField(default=True) # vert, or horizontal, if no wrap
    font = models.CharField(max_length=64, blank=True,
                            default='100% sans-serif')
    
    def __str__(self):
        return self.name


class Presentation(models.Model):
    class Meta:
        constraints = [
            UniqueConstraint(fields=['form', 'name'], name='unique_form_slug')
        ]
    
    form = models.ForeignKey(f_models.Form, models.CASCADE,
                             related_name='presentations',
                             related_query_name='presentation')
    template = models.ForeignKey(Template, models.CASCADE,
                                 null=True, blank=True,
                                 related_name='presentations',
                                 related_query_name='presentation')
    name = models.SlugField(max_length=32, allow_unicode=True,
                            verbose_name='identifier')
    created = models.DateTimeField(auto_now_add=True)
    

class Reference(f_models.RankedModel):
    class Meta:
        constraints = [
            UniqueConstraint(fields=['presentation', '_rank'],
                             name='unique_presentation_rank')
        ]
        ordering = ['presentation', '_rank']
    
    presentation = models.ForeignKey(Presentation, models.CASCADE,
                                     related_name='refereneces',
                                     related_query_name='reference')
    # if no collection, name identifies the (stock or custom) block
    collection = models.SlugField(max_length=32, allow_unicode=True, blank=True)
    # if no name, reference is to the item file for the specified collection
    name = models.SlugField(max_length=32, allow_unicode=True, blank=True)
    # if a composite block, can also give a field name (e.g., state for address)
    field = models.CharField(max_length=32, blank=True)
    
    section = models.ForeignKey(TemplateSection, models.SET_NULL,
                                null=True, blank=True, related_name='+')
    block_label = models.CharField(max_length=256, blank=True) # in markdown
    inline_label = models.CharField(max_length=128, blank=True)
    options = models.JSONField(default=dict, blank=True)
    
    # fields used when a collection is specified:
    block_combine = models.BooleanField(default=False)
    inline_combine = models.CharField(max_length=16, blank=True) # separator
    # if not combined, and no select section specified, it's added to the bottom
    select_section = models.ForeignKey(TemplateSection, models.SET_NULL,
                                       null=True, blank=True, related_name='+')
