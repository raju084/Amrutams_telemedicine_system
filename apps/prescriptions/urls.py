from django.urls import path
from apps.prescriptions.views import (
    PrescriptionCreateView,
    PrescriptionDetailView,
    PrescriptionVerifySignatureView,
)

urlpatterns = [
    path('', PrescriptionCreateView.as_view(), name='prescription-create'),
    path('<uuid:pk>/', PrescriptionDetailView.as_view(), name='prescription-detail'),
    path('<uuid:pk>/verify-signature/', PrescriptionVerifySignatureView.as_view(), name='prescription-verify-signature'),
]
