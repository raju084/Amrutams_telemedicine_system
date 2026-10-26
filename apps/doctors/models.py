import uuid
import secrets
from decimal import Decimal
from django.db import models
from django.utils import timezone
from apps.common.models import UUIDTimeStampedModel
from apps.users.models import User

class Doctor(UUIDTimeStampedModel):
    SPECIALIZATION_CHOICES = (
        ('KAYACHIKITSA', 'Kayachikitsa (Internal Medicine)'),
        ('PANCHAKARMA', 'Panchakarma (Detoxification & Purification)'),
        ('NADI_PARIKSHA', 'Nadi Pariksha (Pulse Diagnosis)'),
        ('SHALYA_TANTRA', 'Shalya Tantra (Ayurvedic Surgery & Wound Care)'),
        ('PRASUTI_STRIROGA', 'Prasuti & Striroga (Women Health & Fertility)'),
        ('KAUMARABHRITYA', 'Kaumarabhritya (Pediatrics)'),
        ('SHALAKYA_TANTRA', 'Shalakya Tantra (ENT & Ophthalmology)'),
        ('RASAYANA_VAJIKARANA', 'Rasayana & Vajikarana (Rejuvenation & Longevity)'),
        ('DERMATOLOGY', 'Ayurvedic Dermatology & Skin Care'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='doctor_profile')
    license_number = models.CharField(max_length=100, unique=True, db_index=True)
    specialization = models.CharField(max_length=50, choices=SPECIALIZATION_CHOICES, db_index=True)
    qualification = models.CharField(max_length=200, help_text="e.g. BAMS, MD (Ayurveda)")
    experience_years = models.PositiveIntegerField(default=1, db_index=True)
    consultation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('500.00'), db_index=True)
    bio = models.TextField(blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('5.00'), db_index=True)
    total_reviews = models.PositiveIntegerField(default=0)
    is_verified = models.BooleanField(default=False, db_index=True)
    digital_signature_key = models.CharField(max_length=64, default=secrets.token_hex)

    class Meta:
        indexes = [
            models.Index(fields=['specialization', 'is_verified']),
            models.Index(fields=['consultation_fee', 'rating']),
        ]

    def __str__(self):
        return f"Dr. {self.user.get_full_name() or self.user.email} - {self.get_specialization_display()}"


class AvailabilitySlot(UUIDTimeStampedModel):
    STATUS_AVAILABLE = 'AVAILABLE'
    STATUS_LOCKED = 'LOCKED'
    STATUS_BOOKED = 'BOOKED'

    STATUS_CHOICES = (
        (STATUS_AVAILABLE, 'Available'),
        (STATUS_LOCKED, 'Locked (In-Checkout)'),
        (STATUS_BOOKED, 'Booked'),
    )

    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='slots')
    date = models.DateField(db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_AVAILABLE, db_index=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    lock_token = models.UUIDField(null=True, blank=True, db_index=True)
    version = models.PositiveIntegerField(default=1)  # Optimistic concurrency versioning

    class Meta:
        unique_together = ('doctor', 'date', 'start_time')
        indexes = [
            models.Index(fields=['doctor', 'date', 'status']),
            models.Index(fields=['status', 'locked_at']),
        ]
        ordering = ['date', 'start_time']

    def is_lock_expired(self, timeout_seconds=600):
        if self.status != self.STATUS_LOCKED or not self.locked_at:
            return False
        return (timezone.now() - self.locked_at).total_seconds() > timeout_seconds

    def __str__(self):
        return f"Slot {self.doctor} on {self.date} {self.start_time}-{self.end_time} [{self.status}]"
