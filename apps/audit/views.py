from rest_framework import generics, permissions, status, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, inline_serializer
from apps.audit.models import AuditLog
from apps.audit.serializers import AuditLogSerializer
from apps.common.permissions import IsAuditor

class AuditLogListView(generics.ListAPIView):
    """
    List compliance audit trail with filtering by action, user, or date.
    Restricted to Compliance Auditors and Admins.
    """
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated, IsAuditor]

    @extend_schema(tags=['Compliance & Audit Trails'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        queryset = AuditLog.objects.all().order_by('-timestamp')
        action = self.request.query_params.get('action')
        user_id = self.request.query_params.get('user_id')
        resource_type = self.request.query_params.get('resource_type')

        if action:
            queryset = queryset.filter(action__icontains=action)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if resource_type:
            queryset = queryset.filter(resource_type__iexact=resource_type)
        return queryset


class AuditLogVerifyChainView(APIView):
    """
    Cryptographic verification of audit log chain integrity.
    Validates that no records have been altered, injected, or removed.
    """
    permission_classes = [permissions.IsAuthenticated, IsAuditor]

    @extend_schema(
        tags=['Compliance & Audit Trails'],
        responses={
            200: inline_serializer(
                name='AuditChainVerifyResponse',
                fields={
                    'success': serializers.BooleanField(),
                    'chain_integrity': serializers.CharField(),
                    'verified_records_count': serializers.IntegerField(),
                    'tampered_records': serializers.ListField(child=serializers.DictField()),
                    'compliance_standard': serializers.CharField(),
                }
            )
        }
    )
    def get(self, request):
        logs = AuditLog.objects.order_by('timestamp').all()
        total_logs = len(logs)
        expected_prev_hash = "GENESIS_ROOT_HASH"
        tampered_records = []

        for log in logs:
            if log.previous_log_hash != expected_prev_hash:
                tampered_records.append({
                    'log_id': str(log.id),
                    'error': 'Broken hash chain link',
                    'expected_prev': expected_prev_hash,
                    'actual_prev': log.previous_log_hash
                })

            recalculated = log.compute_hash()
            if recalculated != log.log_hash:
                tampered_records.append({
                    'log_id': str(log.id),
                    'error': 'Payload mismatch / data tampering',
                    'expected_hash': recalculated,
                    'stored_hash': log.log_hash
                })

            expected_prev_hash = log.log_hash

        is_intact = len(tampered_records) == 0
        return Response({
            'success': True,
            'chain_integrity': 'VALID' if is_intact else 'COMPROMISED',
            'verified_records_count': total_logs,
            'tampered_records': tampered_records,
            'compliance_standard': 'DISHA / HIPAA Title II Security Rule'
        })
