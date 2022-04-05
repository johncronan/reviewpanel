from django import forms
from django.contrib import admin
from django.contrib.admin.views.main import ChangeList
from django.db.models import Q, Count, Subquery, OuterRef
from django.db.models.functions import Coalesce
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from functools import partial

from formative.admin import site
from formative.models import Form, SubmissionRecord
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


@admin.action(description='Add users to panel')
def add_to_panel(modeladmin, request, queryset):
    if 'panel' in request.POST:
        panel = get_object_or_404(Panel, id=int(request.POST['panel']))
        panel.panelists.add(*queryset)
        modeladmin.message_user(request,
                                f'Users added to panel "{panel.name}".')
        return HttpResponseRedirect(request.get_full_path())
    
    class PanelForm(forms.Form):
        panel = forms.ModelChoiceField(queryset=Panel.objects.all())
    
    template_name = 'admin/reviewpanel/add_to_panel.html'
    context = {
        **modeladmin.admin_site.each_context(request),
        'opts': modeladmin.model._meta, 'users': queryset,
        'form': PanelForm(), 'title': 'Add to panel'
    }
    return TemplateResponse(request, template_name, context)


class PanelistInline(admin.TabularInline):
    model = Panel.panelists.through
    extra = 0
    verbose_name = 'panelist'
    verbose_name_plural = 'panelists'


@admin.register(Panel, site=site)
class PanelAdmin(admin.ModelAdmin):
    list_display = ('name', 'program')
    list_filter = ('program',)
    inlines = [PanelistInline]
    exclude = ('panelists',)


class CohortMemberInline(admin.TabularInline):
    model = CohortMember
    extra = 0
    
#    def get_formset(self, request, obj=None, **kwargs): TODO


@admin.register(Cohort, site=site)
class CohortAdmin(admin.ModelAdmin):
    list_display = ('name', 'panel', 'status', 'form')
    list_filter = ('panel', 'status', 'form')
    inlines = [CohortMemberInline]
    readonly_fields = ('primary_input',)
    
    def get_formsets_with_inlines(self, request, obj=None):
        for inline in self.get_inline_instances(request, obj):
            if not isinstance(inline, CohortMemberInline) or obj is not None:
                yield inline.get_formset(request, obj), inline
    
    def primary_input(self, obj):
        input = obj.inputs.order_by('_rank')[:1]
        return input[0] if input else None


class ScoreTypeFilter(admin.SimpleListFilter):
    title = 'value'
    parameter_name = 'value'
    
    def lookups(self, request, model_admin):
        return (('yes', 'scored'), ('skip', 'skipped'), ('no', 'unscored'))
    
    def queryset(self, request, queryset):
        bool_type = Input.InputType.BOOLEAN
        if self.value() == 'yes':
            return queryset.filter(Q(value__gt=0) |
                                   Q(value=0) & Q(input__type=bool_type))
        elif self.value() == 'skip':
            return queryset.filter(value=0).exclude(input__type=bool_type)
        elif self.value() == 'no': return queryset.filter(value__isnull=True)


@admin.register(Score, site=site)
class ScoreAdmin(admin.ModelAdmin):
    list_display = ('submission', 'panelist', 'input', 'cohort', 'display_val',
                    'created')
    list_filter = ('panelist', 'input', 'cohort', 'form', ScoreTypeFilter)
    
    @admin.display(ordering='value', description='value')
    def display_val(self, obj):
        if obj.input.type == Input.InputType.TEXT: return obj.text
        if obj.value is None: return '[unscored]'
        if obj.input.type == Input.InputType.BOOLEAN: return bool(obj.value)
        if not obj.value: return '[skipped]'
        return obj.value


class FormChangeList(ChangeList):
    def url_for_result(self, result):
        name = result.program.slug + '_' + result.slug
        return reverse('admin:%s_%s_changelist' % (self.opts.app_label, name),
                       current_app=self.model_admin.admin_site.name)

class ProgramFormsAdmin(admin.ModelAdmin):
    list_display = ('name', 'submitted', 'created', 'modified')
    list_select_related = ('program',)
    
    def get_changelist(self, request, **kwargs):
        return FormChangeList
    
    def get_queryset(self, request):
        slug = self.model._meta.program_slug
        forms = self.model.objects.exclude(status=Form.Status.DRAFT)
        forms = forms.filter(program__slug=slug)
        args = {'program__slug': slug, 'form': OuterRef('slug')}
        args.update(type=SubmissionRecord.RecordType.SUBMISSION, deleted=False)
        subquery = SubmissionRecord.objects.filter(**args)
        count = subquery.values('form').annotate(count=Count('*'))
        annotation = Coalesce(Subquery(count.values('count')), 0)
        return forms.annotate(submitted=annotation)
    
    def submitted(self, obj):
        return obj.submitted


class FormSubmissionsAdmin(admin.ModelAdmin):
    list_display = ('submission_id', '_created', '_modified')
    
    def has_module_permission(self, request):
        return False # it's linked to by ProgramFormsAdmin, don't show in index
    
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
    
    def get_queryset(self, request):
        return self.model.objects.exclude(_submitted__isnull=True)
    
    @admin.display(description='ID')
    def submission_id(self, obj):
        return str(obj)
