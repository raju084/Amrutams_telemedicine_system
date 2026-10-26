from rest_framework import serializers
from apps.audit.models import AuditLog

class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = (
            'id', 'timestamp', 'user_id', 'user_email', 'user_role',
            'action', 'resource_type', 'resource_id', 'ip_address',
            'user_agent', 'correlation_id', 'payload_diff',
            'previous_log_hash', 'log_hash'
        )
