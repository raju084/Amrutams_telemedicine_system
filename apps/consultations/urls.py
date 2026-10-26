from django.urls import path
from apps.consultations.views import (
    ConsultationCreateView,
    ConsultationListView,
    ConsultationDetailView,
    ConsultationTransitionView,
    ConsultationVideoTokenView,
)

urlpatterns = [
    path('', ConsultationListView.as_view(), name='consultation-list'),
    path('book/', ConsultationCreateView.as_view(), name='consultation-book'),
    path('<uuid:pk>/', ConsultationDetailView.as_view(), name='consultation-detail'),
    path('<uuid:pk>/transition/', ConsultationTransitionView.as_view(), name='consultation-transition'),
    path('<uuid:pk>/video-token/', ConsultationVideoTokenView.as_view(), name='consultation-video-token'),
]
