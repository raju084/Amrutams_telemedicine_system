from django.urls import path
from apps.payments.views import (
    PaymentInitiateView,
    PaymentWebhookView,
    PaymentDetailView,
)

urlpatterns = [
    path('initiate/', PaymentInitiateView.as_view(), name='payment-initiate'),
    path('webhook/', PaymentWebhookView.as_view(), name='payment-webhook'),
    path('<uuid:pk>/', PaymentDetailView.as_view(), name='payment-detail'),
]
