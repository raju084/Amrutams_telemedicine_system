from rest_framework import serializers
from apps.prescriptions.models import Prescription, PrescriptionItem
from apps.consultations.models import Consultation

class PrescriptionItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrescriptionItem
        fields = (
            'id', 'medicine_name', 'form', 'dosage',
            'frequency', 'timing', 'anupana', 'duration_days', 'instructions'
        )


class PrescriptionCreateSerializer(serializers.ModelSerializer):
    items = PrescriptionItemSerializer(many=True)

    class Meta:
        model = Prescription
        fields = (
            'consultation', 'diagnosis', 'dietary_advice',
            'lifestyle_recommendations', 'follow_up_date', 'items'
        )

    def validate_consultation(self, value):
        if hasattr(value, 'prescription'):
            raise serializers.ValidationError("A prescription already exists for this consultation.")
        if value.status not in (Consultation.STATUS_IN_PROGRESS, Consultation.STATUS_COMPLETED):
            raise serializers.ValidationError("Prescriptions can only be issued during or after consultation.")
        return value


class PrescriptionDetailSerializer(serializers.ModelSerializer):
    items = PrescriptionItemSerializer(many=True, read_only=True)
    doctor_name = serializers.CharField(source='consultation.doctor.user.get_full_name', read_only=True)
    patient_name = serializers.CharField(source='consultation.patient.get_full_name', read_only=True)
    consultation_id = serializers.UUIDField(source='consultation.id', read_only=True)

    class Meta:
        model = Prescription
        fields = (
            'id', 'consultation_id', 'doctor_name', 'patient_name',
            'diagnosis', 'dietary_advice', 'lifestyle_recommendations',
            'follow_up_date', 'digital_signature', 'signature_timestamp',
            'items', 'created_at'
        )
