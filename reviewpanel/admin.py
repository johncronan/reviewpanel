from django import forms
from django.contrib import admin, messages
from django.contrib.admin.views.main import ChangeList
from django.contrib.contenttypes.models import ContentType
from django.db.models import F, Q, Count, Exists, Subquery, OuterRef
from django.db.models.functions import Coalesce
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils.safestring import mark_safe
from django_admin_inline_paginator.admin import TabularInlinePaginated
from functools import partial
import types

from formative.admin import site
from formative.models import Form, SubmissionRecord
from .forms import ReferencesFormSet, ReferenceForm, MetricForm, CohortForm, \
    CohortStatusForm, PresentationForm, MetricsExportForm, CombinedExportForm, \
    PresentationExportForm
from .models import Template, TemplateSection, Reference, Presentation, Input, \
    Panel, Cohort, CohortMember, Score, Metric
from .utils import MetricsTabularExport, CombinedTabularExport, \
     PresentationPrintExport


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
        request._obj_ = obj # TODO the code below could be moved into Form class
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
    form = PresentationForm
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
    
    def get_deleted_objects(self, objs, request):
        to_del, models, perms, protected = super().get_deleted_objects(objs,
                                                                       request)
        for obj in objs:
            for cohort in obj.cohorts.filter(status=Cohort.Status.ACTIVE):
                protected.append(cohort)
        return to_del, models, perms, protected
    
    def view_on_site(self, obj):      # don't need the sites framework
        return obj.get_absolute_url() # getting in the way at the moment


class MetricInline(admin.StackedInline):
    model = Metric
    form = MetricForm
    extra = 0


@admin.register(Input, site=site)
class InputAdmin(admin.ModelAdmin):
    list_display = ('name', 'form')
    list_filter = ('form',)
    exclude = ('_rank',)
    inlines = [MetricInline]


@admin.action(description='Add users to panel')
def add_to_panel(modeladmin, request, queryset):
    if 'panel' in request.POST:
        panel = get_object_or_404(Panel, id=int(request.POST['panel']))
        panel.panelists.add(*queryset)
        msg = f'Users added to panel "{panel.name}".',
        modeladmin.message_user(request, msg, messages.SUCCESS)
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
    
    def get_deleted_objects(self, objs, request):
        to_del, models, perms, protected = super().get_deleted_objects(objs,
                                                                       request)
        for obj in objs:
            for cohort in obj.cohorts.exclude(status=Cohort.Status.INACTIVE):
                protected.append(cohort)
        return to_del, models, perms, protected


class CohortMemberInline(TabularInlinePaginated):
    model = CohortMember
    extra = 0
    per_page = 100
    can_delete = True
    exclude = ('content_type', 'object_id')
    readonly_fields = ('email', 'submitted')
    
    def has_add_permission(self, request, obj=None):
        return False
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        match = request.resolver_match
        cohort = Cohort.objects.get(pk=match.kwargs['object_id'])
        model = cohort.form.model
        if not model: return queryset
        
        obj = model.objects.values('pk').filter(pk=OuterRef('object_id'))
        qs = queryset.annotate(email=Subquery(obj.values('_email')),
                               submitted=Subquery(obj.values('_submitted')))
        return qs.order_by('-submitted')
    
    def email(self, object):
        return object.email # TODO: link to the submission change view
    
    def submitted(self, object):
        return object.submitted


@admin.register(Cohort, site=site)
class CohortAdmin(admin.ModelAdmin):
    form = CohortForm
    list_display = ('name', 'panel', 'status', 'form')
    list_filter = ('panel', 'status', 'form')
    inlines = [CohortMemberInline]
    readonly_fields = ('primary_input', 'size')
    actions = ['change_status']
    
    def get_formsets_with_inlines(self, request, obj=None):
        for inline in self.get_inline_instances(request, obj):
            if not isinstance(inline, CohortMemberInline) or obj is not None:
                yield inline.get_formset(request, obj), inline
    
    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if change: # save the cohort again with an updated size count
            obj = form.instance
            obj.size = obj.cohortmember_set.count()
            self.save_model(request, obj, form, change)
    
    def primary_input(self, obj):
        input = obj.inputs.order_by('_rank')[:1]
        return input[0] if input else None
    
    @admin.action(description='Change status of selected cohorts')
    def change_status(self, request, queryset):
        if '_submit' in request.POST:
            status, message = request.POST['status'], request.POST['message']
            if message: n = queryset.update(status=status, message=message)
            else: n = queryset.update(status=status)
            
            msg = f'Status changed for {n} cohorts.'
            self.message_user(request, msg, messages.SUCCESS)
            return HttpResponseRedirect(request.get_full_path())
        
        template_name = 'admin/reviewpanel/cohort_status.html'
        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta, 'media': self.media,
            'cohorts': queryset, 'title': 'Change Cohort Status',
            'form': CohortStatusForm()
        }
        return TemplateResponse(request, template_name, context)


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
    readonly_fields = ('submission_link',)
    
    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        if obj: return tuple(f for f in fields
                             if f not in ('content_type', 'object_id'))
        return fields
    
    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if obj: fields += ('panelist', 'form')
        return fields
    
    @admin.display(ordering='value', description='value')
    def display_val(self, obj):
        if obj.input.type == Input.InputType.TEXT: return obj.text
        if obj.value is None: return '[unscored]'
        if obj.input.type == Input.InputType.BOOLEAN: return bool(obj.value)
        if not obj.value: return '[skipped]'
        return obj.value
    
    @admin.display(description='submission')
    def submission_link(self, obj):
        name = obj.form.program.db_slug + '_' + obj.form.db_slug
        url = reverse('admin:reviewpanel_%s_change' % (name,),
                      args=(obj.object_id,),
                      current_app=self.admin_site.name)
        return mark_safe(f'<a href="{url}">{obj.submission}</a>')


class FormChangeList(ChangeList):
    def url_for_result(self, result):
        name = result.program.db_slug + '_' + result.db_slug
        return reverse('admin:%s_%s_changelist' % (self.opts.app_label, name),
                       current_app=self.model_admin.admin_site.name)

class ProgramFormsAdmin(admin.ModelAdmin):
    list_display = ('name', 'submitted', 'created', 'modified')
    list_select_related = ('program',)
    actions = ['export_ods']
    
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
    
    def get_changelist(self, request, **kwargs):
        return FormChangeList
    
    def get_queryset(self, request):
        slug = self.model._meta.program_slug
        forms = self.model.objects.exclude(status=Form.Status.DRAFT)
        forms = forms.filter(program__slug=slug)
        
        # w/ SubmissionRecord we can get totals for multiple forms using 1 table
        args = {'program__slug': slug, 'form': OuterRef('slug')}
        args.update(type=SubmissionRecord.RecordType.SUBMISSION, deleted=False)
        subquery = SubmissionRecord.objects.filter(**args)
        count = subquery.values('form').annotate(count=Count('*'))
        annotation = Coalesce(Subquery(count.values('count')), 0)
        return forms.annotate(submitted=annotation)
    
    def submitted(self, obj):
        return obj.submitted
    
    @admin.action(description='Export form submissions as ODS')
    def export_ods(self, request, queryset):
        if '_export' in request.POST:
            filename = f'{self.model._meta.program_slug}_export_selected.ods'
            args = { k: request.POST[k] for k in request.POST
                     if k in ('metrics',
                              'text_inputs') or k.endswith('_collections') }
            export = CombinedTabularExport(queryset, **args)
            return export.response_ods(filename, queryset)
        
        template_name = 'admin/reviewpanel/export_forms.html'
        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta, 'media': self.media,
            'forms': queryset, 'title': 'Export Form Submissions',
            'form': CombinedExportForm()
        }
        return TemplateResponse(request, template_name, context)


class BaseScoreFormSet(forms.BaseModelFormSet):
    def __init__(self, instance=None, *args, **kwargs):
        self.instance = instance
        super().__init__(*args, **kwargs)
        scores = Score.objects.filter(object_id=instance.pk)
        self.queryset = scores.order_by('created')
    
    @classmethod
    def get_default_prefix(cls):
        opts = cls.model._meta
        return opts.app_label + '-' + opts.model_name


class SubmissionScoresInline(admin.TabularInline):
    model = Score
    formset = BaseScoreFormSet
    readonly_fields = ('display_val', 'created',)
    
    def has_add_permission(self, request, obj=None): return False
    
    def get_formset(self, request, obj=None, **kwargs):
        fields = ('panelist', 'input', 'cohort',)
        
        defaults = {
            'form': self.form, 'formset': self.formset, 'fields': fields,
            'formfield_callback': partial(self.formfield_for_dbfield,
                                          request=request),
            'extra': 0, 'can_delete': False, 'can_order': False
        }
        return forms.modelformset_factory(self.model, **defaults)
    
    @admin.display(description='value')
    def display_val(self, obj):
        if obj.input.type == Input.InputType.TEXT: return obj.text
        elif obj.input.type == Input.InputType.BOOLEAN: return bool(obj.value)
        if not obj.value: return '[skipped]'
        return obj.value


class CohortListFilter(admin.SimpleListFilter):
    title = 'cohort'
    parameter_name = 'cohort'
    
    def lookups(self, request, model_admin):
        model = model_admin.model
        program_slug, slug = model._meta.program_slug, model._meta.form_slug
        for cohort in Cohort.objects.filter(form__slug=slug,
                                            form__program__slug=program_slug):
            yield (cohort.id, cohort.name)
    
    def queryset(self, request, queryset):
        if not self.value(): return queryset
        cohort_member = CohortMember.objects.filter(object_id=OuterRef('pk'),
                                                    cohort=self.value())
        return queryset.filter(Exists(cohort_member))


class FormSubmissionsAdmin(admin.ModelAdmin):
    list_display = ('submission_id', '_created', '_submitted')
    list_filter = (CohortListFilter,)
    list_per_page = 400
    inlines = [SubmissionScoresInline]
    actions = ['add_to_cohort', 'export_csv', 'export_pdf']
    
    def has_module_permission(self, request):
        return False # it's linked to by ProgramFormsAdmin, don't show in index
    
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
    
    def get_metrics(self, request, **kwargs):
        fs, ps = self.model._meta.form_slug, self.model._meta.program_slug
        form = Form.objects.get(slug=fs, program__slug=ps)
        cohort_id = request.GET.get('cohort')
        
        metrics = Metric.objects.filter(admin_enabled=True,
                                        input__cohort__form=form, **kwargs)
        if cohort_id and cohort_id.isdigit():
            metrics = metrics.filter(input__cohort=int(cohort_id))
        return metrics.distinct(), form
    
    def get_queryset(self, request):
        queryset = self.model.objects.exclude(_submitted__isnull=True)
        
        metrics, _ = self.get_metrics(request)
        scores = Score.objects.all()
        for metric in metrics:
            name = f'metric_{metric.input.name}_{metric.name}'
            annotation = metric.annotation(scores, object_id='pk')
            queryset = queryset.annotate(**{name: annotation})
        
        return queryset
    
    def get_list_display(self, request):
        fields = list(super().get_list_display(request))
        
        metrics, _ = self.get_metrics(request)
        divisors, metric_fields = {}, []
        for metric in metrics.order_by('input', '-count_is_divisor'):
            def field_callable(desc, field, divisor_field=None):
                @admin.display(description=desc, ordering=field)
                def callable(self, obj):
                    v = getattr(obj, field)
                    if v is None: display = '-'
                    elif type(v) not in (int, bool): display = f'{v:.3f}'
                    else: display = v
                    
                    if divisor_field:
                        fv = getattr(obj, divisor_field)
                        if fv: display = f'{display} ({v/fv*100:.1f}%)'
                    return display
                return callable
            
            field_name = 'metric_' + metric.input.name + '_' + metric.name
            input_id, divisor_name = metric.input_id, None
            if metric.type == Metric.MetricType.COUNT and input_id in divisors:
                divisor_name = divisors[metric.input_id]
            if metric.count_is_divisor: divisors[input_id] = field_name

            c = field_callable(metric.name, field_name, divisor_name)
            # Django will reject the ordering if value isn't a field or method:
            setattr(self, field_name, types.MethodType(c, self))
            
            rec = (field_name, metric.position)
            for i, v in enumerate(metric_fields):
                if v[1] > metric.position:
                    metric_fields.insert(i, rec)
                    rec = None
                    break
            if rec: metric_fields.append(rec)
        
        cohort_id, end_fields = request.GET.get('cohort'), []
        if cohort_id and cohort_id.isdigit():
            pres = None
            try: pres = Presentation.objects.get(cohort__pk=int(cohort_id))
            except Presentation.DoesNotExist: pass
            if pres:
                def link_callable(presentation):
                    @admin.display(description='link')
                    def callable(obj):
                        form = presentation.form
                        args = {'program_slug': form.program.slug,
                                'form_slug': form.slug,
                                'pk': obj.pk, 'presentation': presentation.pk}
                        url = reverse('plugins:reviewpanel:submission_admin',
                                      kwargs=args)
                        return mark_safe(f'<a href="{url}">view</a>')
                    return callable
                end_fields.append(link_callable(pres))
        return fields + [ v[0] for v in metric_fields ] + end_fields
    
    @admin.display(description='ID')
    def submission_id(self, obj):
        return str(obj)
    
    @admin.action(description='Add submissions to cohort')
    def add_to_cohort(self, request, queryset):
        if 'cohort' in request.POST:
            cohort = get_object_or_404(Cohort, id=int(request.POST['cohort']))
            ctype = ContentType.objects.get_for_model(cohort.form.model)
            member_subq = CohortMember.objects.filter(cohort=cohort,
                                                      object_id=OuterRef('pk'))
            members = []
            for submission in queryset.exclude(Exists(member_subq)):
                members.append(CohortMember(cohort=cohort, content_type=ctype,
                                            object_id=submission.pk))
            CohortMember.objects.bulk_create(members)
            cohort.size = cohort.cohortmember_set.count()
            cohort.save()
            
            msg = f'Submissions added to cohort "{cohort.name}".'
            self.message_user(request, msg, messages.SUCCESS)
            return HttpResponseRedirect(request.get_full_path())
        
        fs, ps = self.model._meta.form_slug, self.model._meta.program_slug
        qs = Cohort.objects.filter(form__slug=fs, form__program__slug=ps)
        class CohortForm(forms.Form):
            cohort = forms.ModelChoiceField(queryset=qs)
        
        template_name = 'admin/reviewpanel/add_to_cohort.html'
        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta, 'submissions': queryset,
            'form': CohortForm(), 'title': 'Add to cohort'
        }
        return TemplateResponse(request, template_name, context)
    
    @admin.action(description='Export submissions as CSV')
    def export_csv(self, request, queryset):
        metrics, program_form = self.get_metrics(request)
        if '_export' in request.POST:
            args = { k: request.POST[k] for k in request.POST
                     if k.startswith('block_') or k.startswith('collection_')
                        or k.startswith('cfield_') or k.startswith('metric_')
                        or k.startswith('input_') }
            export = MetricsTabularExport(program_form, queryset, **args)
            filename = f'{program_form.slug}_export_selected.csv'
            return export.csv_response(filename, queryset)
        
        inputs = Input.objects.filter(cohort__form=program_form,
                                      type=Input.InputType.TEXT)
        
        template_name = 'admin/formative/export_submissions.html'
        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta, 'media': self.media,
            'submissions': queryset, 'title': 'Export Submissions Data',
            'form': MetricsExportForm(program_form=program_form,
                                      metrics=metrics, inputs=inputs)
        }
        return TemplateResponse(request, template_name, context)
    
    @admin.action(description='Export submissions as PDF')
    def export_pdf(self, request, queryset):
        metrics, form = self.get_metrics(request, panelist_enabled=True)
        if '_export' in request.POST:
            pres = get_object_or_404(Presentation,
                                     id=int(request.POST['presentation']))
            
            filename = f'{form.slug}_export.pdf'
            args = { k: request.POST[k] for k in request.POST
                     if k == 'orientation' or k.startswith('metric_') }
            export = PresentationPrintExport(filename, pres, **args)
            return export.response(queryset)
        
        template_name = 'admin/reviewpanel/report_submissions.html'
        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta, 'media': self.media,
            'submissions': queryset, 'title': 'Export Submissions Report',
            'form': PresentationExportForm(program_form=form, metrics=metrics)
        }
        return TemplateResponse(request, template_name, context)
