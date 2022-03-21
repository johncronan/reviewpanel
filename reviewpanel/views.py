from django.views import generic
from django.shortcuts import get_object_or_404

from formative.models import Form
from .forms import ScoresForm
from .models import Cohort


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
        
        return form.model.objects.all()


class SubmissionDetailView(SubmissionObjectMixin, generic.DetailView):
    template_name = 'reviewpanel/submission.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # TODO
        return context


class ScoresFormView(SubmissionObjectMixin, generic.FormView):
    template_name = 'reviewpanel/submission.html'
    form_class = ScoresForm


class SubmissionView(generic.View):
    def get(self, request, *args, **kwargs):
        return SubmissionDetailView.as_view()(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        return ScoresFormView.as_view()(request, *args, **kwargs)
