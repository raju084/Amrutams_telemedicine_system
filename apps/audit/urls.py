from django.urls import path
from apps.audit.views import AuditLogListView, AuditLogVerifyChainView

urlpatterns = [
    path('', AuditLogListView.as_view(), name='audit-log-list'),
    path('verify-chain/', AuditLogVerifyChainView.as_view(), name='audit-verify-chain'),
]
