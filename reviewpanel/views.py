from django.http import HttpResponseRedirect, HttpResponseBadRequest
from django.views import generic
from django.core.paginator import Paginator
from django.db.models import F, Q, Count, Exists, Subquery, OuterRef
from django.db.models.functions import Coalesce
from django.db.models.lookups import Exact
from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from random import random

from formative.models import Program, Form
from .forms import ScoresForm
from .models import Cohort, CohortMember, Score, Input


URL_PREFIX = 'plugins:reviewpanel:'
SCORES_PER_PAGE = 50


class ProgramView(LoginRequiredMixin, generic.DetailView):
    model = Program
    context_object_name = 'program'
    template_name = 'reviewpanel/program_index.html'
    show_all = False
    
    def get_object(self):
        if self.show_all: return None
        return super().get_object()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.show_all:
            programs = Program.objects.filter(
                form__cohort__panel__panelists=self.request.user
            ).exclude(form__cohort__status=Cohort.Status.INACTIVE)
        else: programs = [self.object]
        
        through, user = Cohort.inputs.through, self.request.user
        input_q = through.objects.filter(cohort=OuterRef('cohort'))
        primary = Subquery(input_q.order_by('input___rank').values('input')[:1])
        
        forms = {}
        for program in programs:
            q = Score.objects.filter(value__gt=0, panelist=user,
                                     cohort=OuterRef('pk'))
            scored = q.annotate(p=primary).filter(input=F('p')).values('cohort')
            scored_count = scored.annotate(c=Count('*')).values('c')
            cohorts_qs = Cohort.objects.filter(form__program=program,
                                               panel__panelists=user)
            vals = cohorts_qs.values('form__slug', 'form__name', 'status')
            cohort_counts = vals.annotate(count=Coalesce(Subquery(scored_count),
                                                         0))
            forms[program] = {}
            for c in cohort_counts:
                default = {'active_scored': 0, 'completed_scored': 0,
                           'active': False}
                form = forms[program].setdefault(c['form__slug'], default)
                form['name'] = c['form__name']
                if c['status'] == Cohort.Status.ACTIVE:
                    form['active_scored'] = c['count']
                    form['active'] = True
                elif c['status'] == Cohort.Status.COMPLETED:
                    form['completed_scored'] = c['count']
        
        context['forms'] = forms
        return context


class FormObjectMixin(generic.detail.SingleObjectMixin):
    context_object_name = 'program_form'
    slug_url_kwarg = 'form_slug'
    
    def get_queryset(self):
        return Form.objects.filter(program__slug=self.kwargs['program_slug'])


class FormInfoView(LoginRequiredMixin, FormObjectMixin, generic.DetailView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        cohorts = Cohort.objects.filter(panel__panelists=self.request.user,
                                        form=self.object)
        cohorts = cohorts.exclude(status=Cohort.Status.INACTIVE)
        messages, cohort_active = ([], []), False
        for cohort in cohorts:
            active = int(cohort.status == Cohort.Status.ACTIVE)
            if active: cohort_active = True
            if cohort.message not in messages[active]:
                messages[active].append(cohort.message)
        messages = messages[int(cohort_active)]
        if len(messages) == 1 and not messages[0]: messages[0] = 'All done!'
        
        context.update(cohort_active=cohort_active, messages=messages)
        if 'closed' in self.template_name: return context
        
        if not cohort_active or 'completed' in self.request.GET:
            cohorts = cohorts.filter(status=Cohort.Status.COMPLETED)
            context['completed'] = True
        else: cohorts = cohorts.filter(status=Cohort.Status.ACTIVE)
        
        through = Cohort.inputs.through
        input_q = through.objects.filter(cohort=OuterRef('cohort'))
        primary = Subquery(input_q.order_by('input___rank').values('input')[:1])
        user_scores = Score.objects.filter(panelist=self.request.user,
                                           cohort__in=cohorts.values('pk'),
                                           form=self.object).exclude(value=None)
        scores = user_scores.annotate(pri=primary).filter(input=F('pri'))
        
        paginator = Paginator(scores.order_by('created'), SCORES_PER_PAGE)
        page = self.request.GET.get('page', 1)
        context['page'] = paginator.get_page(page)
        return context


class FormView(LoginRequiredMixin, generic.RedirectView, FormObjectMixin):
    permanent = False
    
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
        return cohorts, cohorts.filter(Exists(unscored_subq))
    
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
        
        active_cohorts, cohorts = self.panelist_cohorts(user)
        
        cohort = self.choose_panel(user, cohorts)
        if not cohort:
            scores = Score.objects.exclude(value=None)
            skipped = scores.filter(panelist=user, value=0,
                                    cohort__in=active_cohorts).order_by('?')[:1]
            if not skipped:
                return reverse(URL_PREFIX + 'form_complete', kwargs=kwargs)
            kwargs['pk'] = str(skipped[0].object_id)
            return reverse(URL_PREFIX + 'submission_skips', kwargs=kwargs)
        
        unscored = None
        try: unscored = Score.objects.get(panelist=user,
                                          cohort=cohort, value=None)
        except Score.DoesNotExist: pass
        
        if unscored: cohort, unscored_id = unscored.cohort, unscored.object_id
        else: unscored_id = None
        
        input = cohort.inputs.order_by('_rank')[0]
        scores = Score.objects.filter(value__gt=0,
                                      form=cohort.form, input=input)
        user_scored = Score.objects.exclude(value=None).filter(panelist=user)
        cohort_scored = user_scored.filter(cohort=cohort).values('object_id')
        
        app_scores = scores.filter(object_id=OuterRef('object_id'))
        app_counts = app_scores.values('object_id').annotate(count=Count('*'))
        counts, members = app_counts.values('count'), cohort.cohortmember_set
        noscore = members.exclude(object_id__in=Subquery(cohort_scored))
        apps = noscore.annotate(scores=Coalesce(Subquery(counts), 0),
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
        entries = CohortMember.objects.filter(object_id=self.object.pk,
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
        prev_on, next_on = False, False
        
        scores = Score.objects.filter(object_id=self.object.pk, panelist=user)
        try: score = scores.get(value=None) # placeholder for an assigned member
        except Score.DoesNotExist: pass
        
        query = scores.filter(cohort__status=Cohort.Status.ACTIVE)
        try: prev = query.exclude(value=None).order_by('-created')[:1].get()
        except Score.DoesNotExist: pass

        if score and score.cohort.status != Cohort.Status.ACTIVE:
            score.delete()
            return context
        if prev and score: # cohort scored w before, made active again
            score.delete() # so delete the assignment and show it as prev scored
        if prev:
            score = prev
            qs = Score.objects.filter(panelist=user, form=score.form)
            prior = qs.filter(Q(created__lt=score.created) |
                             Q(created=score.created) & Q(id__lt=score.id))
            prev_on, next_on = prior.exists(), True
        if not score: return context # TODO: allow link sharing option
        
        query = Cohort.objects.select_related('presentation__template')
        cohort = query.get(pk=score.cohort_id)
        pres, inputs = cohort.presentation, cohort.inputs.order_by('_rank')
        form, references = pres.form, pres.references.order_by('_rank')
        names = Subquery(references.filter(collection='').values('name'))
        cnames = Subquery(references.exclude(collection='').values('collection'))
        blocks = form.blocks.filter(Q(name__in=names) | Q(name__in=cnames))
        
        apps = CohortMember.objects.filter(cohort__panel__panelists=user,
                                           cohort__status=Cohort.Status.ACTIVE,
                                           cohort__form=form)
        apps_count = apps.values('object_id').distinct().count()
        
        through = Cohort.inputs.through
        input_q = through.objects.filter(cohort=OuterRef('cohort'))
        primary = Subquery(input_q.order_by('input___rank').values('input')[:1])
        qs = Score.objects.filter(value__isnull=False, panelist=user, form=form,
                                  cohort__panel__panelists=user,
                                  cohort__status=Cohort.Status.ACTIVE)
        scored = qs.annotate(pri=primary,
                             skip=Exact(F('value'), 0)).filter(input=F('pri'))
        scored_counts = scored.values('skip').annotate(c=Coalesce(Count('*'),
                                                                  0))
        counts = {False: 0, True: 0}
        for c in scored_counts.values('skip', 'c'): counts[c['skip']] += c['c']
        
        initial = {}
        if score.value is not None:
            for score in scores.select_related('input').filter(cohort=cohort):
                val = score.value
                if score.input.type == Input.InputType.TEXT: val = score.text
                if val: initial[score.input.name] = val
        scores_form = ScoresForm(inputs=inputs, allow_skip=cohort.allow_skip,
                                 initial=initial)
        items = {}
        if form.item_model:
            citems = self.object._items.filter(_collection__in=cnames)
            items = self.object._collections(queryset=citems, form=form)
        
        refs, select_refs = {}, {}
        for ref in references:
            refs.setdefault(ref.section.name, []).append(ref)
            
            if not ref.collection: continue
            if ref.collection not in items: items[ref.collection] = []
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
            'form': scores_form, 'prev_on': prev_on, 'next_on': next_on,
            'stats': {'scored': counts[False], 'skipped': counts[True],
                      'total': apps_count}
        })
        return context


class ScoresFormView(LoginRequiredMixin, SubmissionObjectMixin,
                     generic.FormView):
    template_name = 'reviewpanel/submission.html'
    form_class = ScoresForm
    skips = False
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        
        self.inputs = self.cohort.inputs.order_by('_rank')
        kwargs.update(inputs=self.inputs, allow_skip=self.cohort.allow_skip)
        return kwargs
    
    def form_invalid(self, form):
        # shouldn't be possible unless there's form tampering
        return HttpResponseRedirect(request.get_full_path())
    
    def navigate_history(self, queryset, score, prev=False):
        qs = queryset
        if prev: qs = qs.filter(Q(created__lt=score.created) |
                                Q(created=score.created) & Q(id__lt=score.id))
        else: qs = qs.filter(Q(created__gt=score.created) |
                             Q(created=score.created) & Q(id__gt=score.id))
        try: return qs[0]
        except IndexError: return None
    
    def form_valid(self, form):
        user, program_form = self.request.user, self.cohort.form
        
        score = None
        for i, input in enumerate(self.inputs):
            ctype = ContentType.objects.get_for_model(program_form.model)
            args = {'content_type': ctype, 'form': program_form}
            python_val, args['text'] = form.cleaned_data[input.name], ''
            if input.type == Input.InputType.TEXT:
                args['value'], args['text'] = int(bool(python_val)), python_val
            else: args['value'] = int(python_val)
            
            kwargs = {'panelist': user, 'object_id': self.submission.pk,
                      'cohort': self.cohort, 'input': input}
            if not i:
                program_form, id = self.cohort.form, self.submission.pk
                try: score = Score.objects.get(**kwargs)
                except Score.DoesNotExist: return HttpResponseBadRequest()
                
                score.value, score.text = args['value'], args['text']
                score.save()
            elif input.type == Input.InputType.TEXT and not python_val:
                Score.objects.filter(**kwargs).delete()
            else: Score.objects.update_or_create(defaults=args, **kwargs)
        
        request = self.request
        nav = 'prev_scored' in request.POST or 'next_scored' in request.POST
        if nav and not self.skips:
            qs = Score.objects.filter(panelist=user, form=program_form)
            previous = 'prev_scored' in request.POST
            target = self.navigate_history(qs, score, prev=previous)
            
            if not target:
                self.kwargs.pop('pk')
                url = reverse(URL_PREFIX + 'form_index', kwargs=self.kwargs)
            else:
                self.kwargs['pk'] = target.object_id
                url = reverse(URL_PREFIX + 'submission', kwargs=self.kwargs)
            return HttpResponseRedirect(url)
        
        # get another random submission to review
        self.kwargs.pop('pk')
        return FormView.as_view()(self.request, **self.kwargs)
    
    def post(self, request, *args, **kwargs):
        self.submission = self.get_object()
        
        if 'cohort_id' not in request.POST: return HttpResponseBadRequest()
        
        try: self.cohort = Cohort.objects.get(pk=int(request.POST['cohort_id']),
                                              panel__panelists=request.user)
        except ValueError: return HttpResponseBadRequest()
        if self.cohort.status != Cohort.Status.ACTIVE: # this will redir to an
            self.kwargs.pop('pk') # app in cohort still active, or form_complete
            return FormView.as_view()(self.request, **self.kwargs)
        
        return super().post(request, *args, **kwargs)


class SubmissionView(generic.View):
    skips = False
    
    def get(self, request, *args, **kwargs):
        return SubmissionDetailView.as_view()(request, *args, **kwargs)
    
    def post(self, req, *args, **kwargs):
        return ScoresFormView.as_view(skips=self.skips)(req, *args, **kwargs)
