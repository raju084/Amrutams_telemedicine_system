from rest_framework import serializers
from apps.doctors.models import Doctor, AvailabilitySlot
from apps.users.serializers import UserDetailSerializer
from drf_spectacular.utils import extend_schema_field
from datetime import datetime, timedelta, time

class DoctorListSerializer(serializers.ModelSerializer):
    doctor_name = serializers.SerializerMethodField()
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Doctor
        fields = (
            'id', 'doctor_name', 'email', 'specialization',
            'qualification', 'experience_years', 'consultation_fee',
            'rating', 'total_reviews', 'is_verified'
        )

    @extend_schema_field(serializers.CharField)
    def get_doctor_name(self, obj) -> str:
        name = obj.user.get_full_name()
        return f"Dr. {name}" if name else f"Dr. {obj.user.email}"


class DoctorDetailSerializer(serializers.ModelSerializer):
    user = UserDetailSerializer(read_only=True)
    specialization_display = serializers.CharField(source='get_specialization_display', read_only=True)

    class Meta:
        model = Doctor
        fields = (
            'id', 'user', 'license_number', 'specialization',
            'specialization_display', 'qualification', 'experience_years',
            'consultation_fee', 'bio', 'rating', 'total_reviews',
            'is_verified', 'created_at'
        )


class AvailabilitySlotSerializer(serializers.ModelSerializer):
    doctor_id = serializers.UUIDField(source='doctor.id', read_only=True)
    doctor_name = serializers.CharField(source='doctor.user.get_full_name', read_only=True)

    class Meta:
        model = AvailabilitySlot
        fields = (
            'id', 'doctor_id', 'doctor_name', 'date',
            'start_time', 'end_time', 'status'
        )
        read_only_fields = ('id', 'doctor_id', 'doctor_name', 'status')


class SlotBatchCreateSerializer(serializers.Serializer):
    date = serializers.DateField()
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    slot_duration_minutes = serializers.IntegerField(default=30, min_value=15, max_value=120)

    def validate(self, data):
        if data['start_time'] >= data['end_time']:
            raise serializers.ValidationError("start_time must be strictly before end_time.")
        return data
