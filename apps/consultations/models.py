import uuid
from django.db import models
from django.utils import timezone
from apps.common.models import UUIDTimeStampedModel
from apps.users.models import User
from apps.doctors.models import Doctor, AvailabilitySlot
from apps.common.crypto import encrypt_phi, decrypt_phi

class Consultation(UUIDTimeStampedModel):
    STATUS_REQUESTED = 'REQUESTED'       # Slot locked, awaiting payment
    STATUS_CONFIRMED = 'CONFIRMED'       # Paid and scheduled
    STATUS_IN_PROGRESS = 'IN_PROGRESS'   # Live call underway
    STATUS_COMPLETED = 'COMPLETED'       # Ended with/without prescription
    STATUS_CANCELLED = 'CANCELLED'       # Released & refunded if applicable
    STATUS_NO_SHOW = 'NO_SHOW'

    STATUS_CHOICES = (
        (STATUS_REQUESTED, 'Requested (Pending Payment)'),
        (STATUS_CONFIRMED, 'Confirmed & Scheduled'),
        (STATUS_IN_PROGRESS, 'In-Progress (Call Active)'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_NO_SHOW, 'No Show'),
    )

    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='patient_consultations', db_index=True)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='doctor_consultations', db_index=True)
    slot = models.OneToOneField(AvailabilitySlot, on_delete=models.CASCADE, related_name='consultation')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_REQUESTED, db_index=True)
    
    chief_complaint = models.CharField(max_length=255)
    _symptoms_encrypted = models.TextField(blank=True, default='')
    
    video_room_id = models.CharField(max_length=128, blank=True, null=True, unique=True)
    cancellation_reason = models.TextField(blank=True, null=True)
    
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['patient', 'status']),
            models.Index(fields=['doctor', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]

    @property
    def symptoms(self) -> str:
        return decrypt_phi(self._symptoms_encrypted)

    @symptoms.setter
    def symptoms(self, val: str):
        self._symptoms_encrypted = encrypt_phi(val)

    def __str__(self):
        return f"Consultation {self.id} | {self.patient.email} with {self.doctor} [{self.status}]"
