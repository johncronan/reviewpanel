from django.http import HttpResponseRedirect, HttpResponseBadRequest
from django.views import generic
from django.db.models import F, Q, Count, Exists, Subquery, OuterRef
from django.db.models.functions import Coalesce
from django.db.models.lookups import Exact
from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from random import random

from formative.models import Form
from .forms import ScoresForm
from .models import Cohort, CohortMember, Score, Input


class FormView(generic.RedirectView, LoginRequiredMixin,
               generic.detail.SingleObjectMixin):
    permanent = False
    slug_url_kwarg = 'form_slug'
    
    def get_queryset(self):
        return Form.objects.filter(program__slug=self.kwargs['program_slug'])
    
    def panelist_cohorts(self, user):
        # find the cohorts with unseen apps reviewed by panels this user is on
        cohorts = Cohort.objects.filter(status=Cohort.Status.ACTIVE,
                                        form=self.object, panel__panelists=user)
        
        members_subq = CohortMember.objects.filter(cohort=OuterRef('pk'))
        
        # subquery to find a unique cohort for each applicant (overlap possible)
        q = cohorts.filter(cohortmember__object_id=OuterRef('object_id'))
        app_cohort = Subquery(q.order_by('size', '-created').values('pk')[:1])
        apps = members_subq.annotate(app_cohort=app_cohort)
        
        # annotate cohorts with whether there's app w/ no input for that cohort
        app_cohort_score_subsubq = Score.objects.exclude(value=None).filter(
            panelist=user, content_type=OuterRef('content_type'),
            object_id=OuterRef('object_id'), cohort=OuterRef('app_cohort')
        )
        unscored_subq = apps.exclude(Exists(app_cohort_score_subsubq))
        return cohorts.filter(Exists(unscored_subq))
    
    def choose_panel(self, user, cohorts):
        total, weights = 0, {}
        for cohort in cohorts.annotate(weight=F('panel_weight') * F('size')):
            weights[cohort] = cohort.weight
            total += cohort.weight
        if not weights: return None
        if not total:
            weights, total = { cohort: 1 for cohort in weights }, len(weights)
        
        r, v = random(), 0
        for cohort, weight in weights.items():
            v += weight / total
            if r < v: return cohort
        return cohort
    
    def get_redirect_url(self, *args, **kwargs):
        self.object = self.get_object()
        form, user = self.object, self.request.user
        
        cohorts = self.panelist_cohorts(user)
        
        ctype = ContentType.objects.get_for_model(form.model)
        unscored = None
        try: unscored = Score.objects.get(panelist=user, content_type=ctype,
                                          cohort__in=cohorts, value=None)
        except Score.DoesNotExist: pass
        
        if unscored: cohort, unscored_id = unscored.cohort, unscored.object_id
        else:
            cohort = self.choose_panel(user, cohorts)
            if not cohort:
                url = reverse('plugins:reviewpanel:form_complete',
                              kwargs=kwargs)
                return HttpResponseRedirect(url)
            unscored_id = None
        
        input = cohort.inputs.order_by('_rank')[0]
        scores = Score.objects.filter(value__gt=0,
                                      form=cohort.form, input=input)
        user_scored = Score.objects.exclude(value=None).filter(panelist=user)
        cohort_scored = user_scored.filter(cohort=cohort).values('object_id')
        
        app_scores = scores.filter(object_id=OuterRef('object_id'))
        app_counts = app_scores.values('object_id').annotate(count=Count('*'))
        counts, members = app_counts.values('count'), cohort.cohortmember_set
        unscored = members.exclude(object_id__in=Subquery(cohort_scored))
        apps = unscored.annotate(scores=Coalesce(Subquery(counts), 0),
                                 put_first=Exact(F('object_id'), unscored_id))
        chosen, first = None, None
        for member in apps.order_by('-put_first', 'scores', '?')[:2]:
            if member.put_first:
                first = member
                continue
            lowest_count = member.scores
            if first and unscored:
                if first.scores <= lowest_count: chosen = first
                else: unscored.delete() # panelist waited; it will come up later
            if not chosen: chosen = member
        if not chosen: chosen = first
        
        score = Score.objects.create_for_cohort(user, cohort, input=input,
                                                submission=chosen.member)
        if chosen != first: score.save()
        kwargs['pk'] = str(chosen.object_id)
        return reverse('plugins:reviewpanel:submission', kwargs=kwargs)


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
        scores_form = ScoresForm(inputs=inputs, allow_skip=cohort.allow_skip)
        
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
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        
        self.inputs = self.cohort.inputs.order_by('_rank')
        kwargs.update(inputs=self.inputs, allow_skip=self.cohort.allow_skip)
        return kwargs
    
    def form_invalid(self, form):
        # shouldn't be possible unless there's form tampering
        return HttpResponseRedirect(request.get_full_path())
    
    def form_valid(self, form):
        scores = []
        for i, input in enumerate(self.inputs):
            args = {'input': input, 'submission': self.submission}
            python_val, args['text'] = form.cleaned_data[input.name], ''
            if input.type == Input.InputType.TEXT:
                args['value'], args['text'] = int(bool(python_val)), python_val
            else: args['value'] = int(python_val)
            
            user = self.request.user
            if not i:
                program_form, id = self.cohort.form, self.submission.pk
                ctype = ContentType.objects.get_for_model(program_form.model)
                try: score = Score.objects.get(panelist=user, object_id=id,
                                               content_type=ctype, input=input)
                except Score.DoesNotExist: return HttpResponseBadRequest()
                
                score.value, score.text = args['value'], args['text']
                score.save()
                continue
            elif input.type == Input.InputType.TEXT and not python_val: continue
            
            score = Score.objects.create_for_cohort(user, self.cohort, **args)
            scores.append(score)
        Score.objects.bulk_create(scores)
        
        # if we're in the previously scored submissions TODO
        
        # get another random submission to review
        self.kwargs.pop('pk')
        return FormView.as_view()(self.request, **self.kwargs)
    
    def post(self, request, *args, **kwargs):
        self.submission = self.get_object()
        
        if 'cohort_id' not in request.POST: return HttpResponseBadRequest()
        # TODO: check that the panelist is reviewing this cohort
        try: self.cohort = Cohort.objects.get(pk=int(request.POST['cohort_id']),
                                              status=Cohort.Status.ACTIVE)
        except ValueError: return HttpResponseBadRequest()
        
        return super().post(request, *args, **kwargs)


class SubmissionView(generic.View):
    def get(self, request, *args, **kwargs):
        return SubmissionDetailView.as_view()(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        return ScoresFormView.as_view()(request, *args, **kwargs)
