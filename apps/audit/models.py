import uuid
import hashlib
import json
from django.db import models
from django.core.exceptions import PermissionDenied

class AuditLog(models.Model):
    """
    Immutable, tamper-evident audit log for HIPAA / DISHA healthcare compliance.
    Each record seals itself into a cryptographic hash chain using SHA-256.
    Once created, rows cannot be updated or deleted.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user_id = models.UUIDField(null=True, blank=True, db_index=True)
    user_email = models.CharField(max_length=255, blank=True, default='')
    user_role = models.CharField(max_length=50, blank=True, default='ANONYMOUS')
    action = models.CharField(max_length=100, db_index=True)
    resource_type = models.CharField(max_length=100, db_index=True)
    resource_id = models.CharField(max_length=100, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True, default='')
    correlation_id = models.CharField(max_length=100, blank=True, default='')
    payload_diff = models.JSONField(default=dict, blank=True)
    
    # Tamper-evident hash chain
    previous_log_hash = models.CharField(max_length=64, blank=True, default='')
    log_hash = models.CharField(max_length=64, editable=False, db_index=True)

    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['action', 'resource_type']),
            models.Index(fields=['user_id', 'timestamp']),
            models.Index(fields=['log_hash']),
        ]

    def compute_hash(self) -> str:
        canonical_content = json.dumps({
            'prev_hash': self.previous_log_hash,
            'user_id': str(self.user_id or ''),
            'action': self.action,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'correlation_id': self.correlation_id,
            'payload': self.payload_diff,
        }, sort_keys=True)
        return hashlib.sha256(canonical_content.encode('utf-8')).hexdigest()

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionDenied("Audit logs are strictly append-only and immutable. Modifying an existing record is prohibited.")

        # Link to previous log hash
        last_log = AuditLog.objects.order_by('-timestamp').first()
        if last_log and last_log.log_hash:
            self.previous_log_hash = last_log.log_hash
        else:
            self.previous_log_hash = "GENESIS_ROOT_HASH"

        self.log_hash = self.compute_hash()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied("Audit logs cannot be deleted. Compliance regulations require immutable retention.")

    def __str__(self):
        return f"[{self.timestamp}] {self.user_email} -> {self.action} on {self.resource_type}:{self.resource_id}"
