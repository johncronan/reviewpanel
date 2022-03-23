from django.urls import path, include

from .views import FormView, SubmissionView


review_patterns = [
    path('<slug:program_slug>/<slug:form_slug>/', include([
        path('', FormView.as_view(), name='form'),
        path('<uuid:pk>/', SubmissionView.as_view(), name='submission')
    ]))
]

urlpatterns = [
    path('review/', include(review_patterns))
]
