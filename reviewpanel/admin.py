from django import forms
from django.contrib import admin
from functools import partial

from formative.admin import site
from .forms import ReferencesFormSet, ReferenceForm
from .models import Template, TemplateSection, Reference, Presentation, Input, \
    Panel, Cohort, CohortMember, Score


class TemplateSectionInline(admin.StackedInline):
    model = TemplateSection
    extra = 0


@admin.register(Template, site=site)
class TemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'program')
    list_filter = ('program',)
    inlines = [TemplateSectionInline]


class ReferenceInline(admin.StackedInline):
    model = Reference
    extra = 0
    formset = ReferencesFormSet
    form = ReferenceForm
    
    def get_formset(self, request, obj=None, **kwargs):
        request._obj_ = obj
        kwargs['formfield_callback'] = partial(self.formfield_for_dbfield,
                                               request=request)
        return super().get_formset(request, obj, **kwargs)
    
    def formfield_for_dbfield(self, db_field, **kwargs):
        field = super().formfield_for_dbfield(db_field, **kwargs)
        pres = kwargs.pop('request')._obj_
        
        if db_field.name in ('section', 'select_section'):
            if pres.template:
                field.queryset = field.queryset.filter(template=pres.template)
            else: field.queryset = field.queryset.none()
        
        elif db_field.name == 'collection':
            choices = [('', '-')]
            for b in pres.form.collections():
                if (b.name, b.name) not in choices:
                    choices.append((b.name, b.name))
            return forms.ChoiceField(choices=choices, required=False, **kwargs)
        
        elif db_field.name == 'name':
            regular_blocks = pres.form.submission_blocks()
            choices = [('', '-')] + [ (n, n) for n in regular_blocks ]
            for b in pres.form.collections():
                for f in b.collection_fields():
                    if (f, f) not in choices: choices.append((f, f))
            return forms.ChoiceField(choices=choices, required=False, **kwargs)
        
        elif db_field.name == 'field':
            return forms.ChoiceField(choices=(), required=False, **kwargs)
        
        return field


@admin.register(Presentation, site=site)
class PresentationAdmin(admin.ModelAdmin):
    list_display = ('name', 'created', 'template', 'form')
    list_filter = ('form',)
    inlines = [ReferenceInline]
    
    def get_formset_kwargs(self, request, obj=None, *args):
        kwargs = super().get_formset_kwargs(request, obj, *args)
        kwargs['presentation'] = obj
        return kwargs
    
    def get_formsets_with_inlines(self, request, obj=None):
        for inline in self.get_inline_instances(request, obj):
            if not isinstance(inline, ReferenceInline) or obj is not None:
                yield inline.get_formset(request, obj), inline


@admin.register(Input, site=site)
class InputAdmin(admin.ModelAdmin):
    list_display = ('name', 'form')
    list_filter = ('form',)
    exclude = ('_rank',)


@admin.register(Panel, site=site)
class PanelAdmin(admin.ModelAdmin):
    list_display = ('name', 'program')
    list_filter = ('program',)


class CohortMemberInline(admin.TabularInline):
    model = CohortMember
    extra = 0


@admin.register(Cohort, site=site)
class CohortAdmin(admin.ModelAdmin):
    list_display = ('name', 'panel', 'status', 'form')
    list_filter = ('panel', 'status', 'form')
    inlines = [CohortMemberInline]


class ScoreTypeFilter(admin.SimpleListFilter):
    title = 'value'
    parameter_name = 'value'
    
    def lookups(self, request, model_admin):
        return (('yes', 'scored'), ('skip', 'skipped'), ('no', 'unscored'))
    
    def queryset(self, request, queryset):
        if self.value() == 'yes': return queryset.filter(value__gt=0)
        elif self.value() == 'skip': return queryset.filter(value=0)
        elif self.value() == 'no': return queryset.filter(value__isnull=True)


@admin.register(Score, site=site)
class ScoreAdmin(admin.ModelAdmin):
    list_display = ('submission', 'panelist', 'input', 'cohort', 'form')
    list_filter = ('panelist', 'input', 'cohort', 'form', ScoreTypeFilter)
