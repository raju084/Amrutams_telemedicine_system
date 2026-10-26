import uuid
from decimal import Decimal
from django.db import models
from apps.common.models import UUIDTimeStampedModel
from apps.consultations.models import Consultation

class Payment(UUIDTimeStampedModel):
    STATUS_PENDING = 'PENDING'
    STATUS_SUCCESS = 'SUCCESS'
    STATUS_FAILED = 'FAILED'
    STATUS_REFUNDED = 'REFUNDED'

    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending'),
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_REFUNDED, 'Refunded'),
    )

    consultation = models.ForeignKey(Consultation, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='INR')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    gateway_order_id = models.CharField(max_length=100, blank=True, db_index=True)
    gateway_payment_id = models.CharField(max_length=100, blank=True, db_index=True)
    idempotency_key = models.CharField(max_length=255, unique=True, db_index=True)
    gateway_response = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"Payment {self.id} [{self.status}] INR {self.amount} for Consultation {self.consultation_id}"
