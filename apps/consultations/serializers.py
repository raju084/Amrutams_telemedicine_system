from rest_framework import serializers
from apps.consultations.models import Consultation
from apps.doctors.serializers import DoctorListSerializer, AvailabilitySlotSerializer
from apps.users.serializers import UserDetailSerializer

class ConsultationCreateSerializer(serializers.Serializer):
    slot_id = serializers.UUIDField()
    chief_complaint = serializers.CharField(max_length=255)
    symptoms = serializers.CharField(required=False, allow_blank=True, default='')


class ConsultationDetailSerializer(serializers.ModelSerializer):
    doctor = DoctorListSerializer(read_only=True)
    patient = UserDetailSerializer(read_only=True)
    slot = AvailabilitySlotSerializer(read_only=True)
    symptoms = serializers.CharField(read_only=True)

    class Meta:
        model = Consultation
        fields = (
            'id', 'patient', 'doctor', 'slot', 'status',
            'chief_complaint', 'symptoms', 'video_room_id',
            'cancellation_reason', 'started_at', 'ended_at',
            'created_at', 'updated_at'
        )


class ConsultationStatusTransitionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['START', 'COMPLETE', 'CANCEL', 'NO_SHOW'])
    reason = serializers.CharField(required=False, allow_blank=True)
