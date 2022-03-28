from django.urls import path, include

from .views import FormView, FormInfoView, SubmissionView


review_patterns = [
    path('<slug:program_slug>/<slug:form_slug>/', include([
        path('', FormView.as_view(), name='form'),
        path('complete', FormInfoView.as_view(
            template_name='reviewpanel/form_complete.html'
        ), name='form_complete'),
        path('submissions/', FormInfoView.as_view(
            template_name='reviewpanel/form_index.html'
        ), name='form_index'),
        path('<uuid:pk>/', SubmissionView.as_view(), name='submission'),
        path('<uuid:pk>/skips', SubmissionView.as_view(skips=True),
             name='submission_skips')
    ]))
]

urlpatterns = [
    path('review/', include(review_patterns))
]
