import uuid
from django.db import models
from django.utils import timezone

class UUIDTimeStampedModel(models.Model):
    """
    Abstract base model providing UUID primary key, automatic timestamping,
    and soft-deletion support.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False, db_index=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']

    def soft_delete(self):
        self.is_deleted = True
        self.save(update_fields=['is_deleted', 'updated_at'])


class IdempotencyRecord(UUIDTimeStampedModel):
    """
    Stores idempotency execution records to prevent duplicate side-effects
    on payment, booking, and prescription writes.
    """
    STATUS_PENDING = 'PENDING'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_FAILED = 'FAILED'

    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
    )

    key = models.CharField(max_length=255, unique=True, db_index=True)
    user_id = models.UUIDField(null=True, blank=True, db_index=True)
    request_path = models.CharField(max_length=255)
    request_method = models.CharField(max_length=10)
    request_hash = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    response_code = models.IntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['key', 'status']),
            models.Index(fields=['expires_at']),
        ]

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"IdempotencyRecord({self.key} - {self.status})"
