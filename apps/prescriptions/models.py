import uuid
from django.db import models
from django.utils import timezone
from apps.common.models import UUIDTimeStampedModel
from apps.consultations.models import Consultation

class Prescription(UUIDTimeStampedModel):
    consultation = models.OneToOneField(Consultation, on_delete=models.CASCADE, related_name='prescription')
    diagnosis = models.TextField(help_text="Clinical diagnosis and Ayurvedic Nidan")
    dietary_advice = models.TextField(blank=True, help_text="Pathya (recommended) & Apathya (prohibited) foods")
    lifestyle_recommendations = models.TextField(blank=True, help_text="Dinacharya & daily routines")
    follow_up_date = models.DateField(null=True, blank=True)
    
    # Tamper-evident digital signature
    digital_signature = models.CharField(max_length=128, blank=True)
    signature_timestamp = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Prescription {self.id} for Consultation {self.consultation_id}"


class PrescriptionItem(UUIDTimeStampedModel):
    TIMING_CHOICES = (
        ('BEFORE_MEALS', 'Before Meals (Pragbhakta)'),
        ('AFTER_MEALS', 'After Meals (Adhobhakta)'),
        ('WITH_MEALS', 'With Meals (Sabhakta)'),
        ('BEDTIME', 'Bedtime (Nishi)'),
    )

    FORM_CHOICES = (
        ('CHURNA', 'Churna (Powder)'),
        ('VATI', 'Vati / Gutika (Tablet)'),
        ('ASAVA_ARISHTA', 'Asava / Arishta (Fermented Liquid)'),
        ('TAILA', 'Taila (Medicated Oil)'),
        ('GHRITA', 'Ghrita (Medicated Ghee)'),
        ('KASHAYA', 'Kashaya (Decoction)'),
        ('AVALEHA', 'Avaleha (Herbal Paste/Jam)'),
        ('SYRUP', 'Syrup'),
    )

    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name='items')
    medicine_name = models.CharField(max_length=200, help_text="e.g., Amrutam Brakey Hair Spa or Ashwagandha Churna")
    form = models.CharField(max_length=30, choices=FORM_CHOICES, default='CHURNA')
    dosage = models.CharField(max_length=100, help_text="e.g. 5g or 1 tablet")
    frequency = models.CharField(max_length=100, help_text="e.g. Twice a day")
    timing = models.CharField(max_length=30, choices=TIMING_CHOICES, default='AFTER_MEALS')
    anupana = models.CharField(max_length=100, default='Warm Water', help_text="Vehicle: Warm water, Honey, Milk, Ghee")
    duration_days = models.PositiveIntegerField(default=14)
    instructions = models.TextField(blank=True)

    def __str__(self):
        return f"{self.medicine_name} ({self.dosage}) - {self.duration_days} days"
