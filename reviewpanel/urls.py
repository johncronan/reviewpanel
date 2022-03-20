from django.urls import path, include

from .views import FormView


review_patterns = [
    path('<slug:program_slug>/<slug:form_slug>/', FormView.as_view(),
         name='form')
]

urlpatterns = [
    path('review/', include(review_patterns))
]
