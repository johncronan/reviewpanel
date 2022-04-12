from django.urls import path, include

from .views import ProgramView, FormView, FormInfoView, SubmissionView, \
    SubmissionAdminView, PresentationAdminView


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
             name='submission_skips'),
        path('<uuid:pk>/<int:presentation>/', SubmissionAdminView.as_view(),
             name='submission_admin'),
        path('<int:presentation>/', PresentationAdminView.as_view(),
             name='presentation_admin')
    ])),
    path('<slug:slug>/', ProgramView.as_view(), name='program_index'),
    path('', ProgramView.as_view(show_all=True), name='index')
]

urlpatterns = [
    path('review/', include(review_patterns))
]
