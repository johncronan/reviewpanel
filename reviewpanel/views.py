from django.http import HttpResponseRedirect
from django.views import generic
from django.db.models import Q, Subquery
from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin

from formative.models import Form
from .forms import ScoresForm
from .models import Cohort, CohortMember, Score


class FormView(generic.RedirectView):
    permanent = False
    
    def get_redirect_url(self, *args, **kwargs):
        return None # TODO


class SubmissionObjectMixin(generic.detail.SingleObjectMixin):
    context_object_name = 'submission'
    
    def get_queryset(self):
        form = get_object_or_404(Form.objects.select_related('program'),
                                 program__slug=self.kwargs['program_slug'],
                                 slug=self.kwargs['form_slug'])
        
        form.model, form.item_model
        return form.model.objects.all()


class SubmissionDetailView(LoginRequiredMixin, SubmissionObjectMixin,
                           generic.DetailView):
    template_name = 'reviewpanel/submission.html'
    
    def render_to_response(self, context, **kwargs):
        user = self.request.user
        entries = CohortMember.objects.filter(object_id=self.object._id,
                                              cohort__panel__panelists=user)
        if not entries.exclude(cohort__status=Cohort.Status.INACTIVE).exists():
            return self.handle_no_permission()
        
        if 'cohort' not in context:
            kwargs = { k: self.kwargs[k] for k in self.kwargs if k != 'pk' }
            return HttpResponseRedirect(reverse('plugins:reviewpanel:form',
                                                kwargs=kwargs))
        
        return super().render_to_response(context, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        score, prev, user = None, None, self.request.user
        
        query = Score.objects.filter(object_id=self.object._id, panelist=user)
        try: score = query.get(value=None) # placeholder for an assigned member
        except Score.DoesNotExist: pass
        
        query = query.filter(cohort__status=Cohort.Status.ACTIVE)
        try: prev = query.exclude(value=None).order_by('-created')[:1].get()
        except Score.DoesNotExist: pass
        if prev or (score and score.cohort.status != Cohort.Status.ACTIVE):
            if score: score.delete() # cohort scored w before, made active again
            score = prev # so delete the assignment and show it as prev scored
        
        if not score: return context
        
        query = Cohort.objects.select_related('presentation__template')
        cohort = query.get(pk=score.cohort_id)
        pres, inputs = cohort.presentation, cohort.inputs.order_by('_rank')
        form, references = pres.form, pres.references.order_by('_rank')
        names = Subquery(references.filter(collection='').values('name'))
        cnames = Subquery(references.exclude(collection='').values('collection'))
        blocks = form.blocks.filter(Q(name__in=names) | Q(name__in=cnames))
        
        if score.value: pass # TODO load the prior scores for the correct cohort
        scores_form = ScoresForm(inputs=inputs)
        
        items = {}
        if form.item_model:
            citems = self.object._items.filter(_collection__in=cnames)
            items = self.object._collections(queryset=citems, form=form)
        
        refs, select_refs = {}, {}
        for ref in references:
            refs.setdefault(ref.section.name, []).append(ref)
            
            if not ref.collection: continue
            section = ref.select_section if ref.select_section else ref.section
            section_refs = select_refs.setdefault(section.name, {})
            collection = section_refs.setdefault(ref.collection, ([], []))
            
            if ref.is_file: collection[0].append(ref)
            else: collection[1].append(ref)
            
        sections = []
        for section in pres.template.sections.order_by('-y'):
            selectors = {}
            # a map from collection to array of refs that want a selector here
            if section.name in select_refs:
                selectors = { col: v[0]+v[1]
                              for col, v in select_refs[section.name].items() }
            sections.append((section,
                             refs[section.name] if section.name in refs else [],
                             selectors))
        
        context.update({
            'cohort': cohort, 'presentation': pres,
            'blocks': { b.name: b for b in blocks }, 'items': items,
            'template': pres.template, 'sections': sections,
            'inputs_section': pres.inputs_section(), 'form': scores_form
        })
        return context


class ScoresFormView(LoginRequiredMixin, SubmissionObjectMixin,
                     generic.FormView):
    template_name = 'reviewpanel/submission.html'
    form_class = ScoresForm


class SubmissionView(generic.View):
    def get(self, request, *args, **kwargs):
        return SubmissionDetailView.as_view()(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        return ScoresFormView.as_view()(request, *args, **kwargs)
