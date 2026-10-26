from rest_framework import serializers
from django.contrib.auth import authenticate
from apps.users.models import User, PatientProfile
from apps.common.crypto import encrypt_phi, decrypt_phi

class PatientProfileSerializer(serializers.ModelSerializer):
    allergies = serializers.CharField(required=False, allow_blank=True)
    chronic_conditions = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = PatientProfile
        fields = (
            'date_of_birth', 'gender', 'blood_group',
            'emergency_contact', 'allergies', 'chronic_conditions',
            'prakriti'
        )

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['allergies'] = instance.allergies
        ret['chronic_conditions'] = instance.chronic_conditions
        return ret


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=10)
    profile = PatientProfileSerializer(required=False)

    class Meta:
        model = User
        fields = ('id', 'email', 'password', 'first_name', 'last_name', 'phone_number', 'role', 'profile')

    def create(self, validated_data):
        profile_data = validated_data.pop('profile', None)
        password = validated_data.pop('password')
        role = validated_data.get('role', User.ROLE_PATIENT)

        user = User.objects.create_user(password=password, **validated_data)

        if role == User.ROLE_PATIENT:
            p = PatientProfile.objects.create(user=user)
            if profile_data:
                for k, v in profile_data.items():
                    setattr(p, k, v)
                p.save()
        return user


class UserDetailSerializer(serializers.ModelSerializer):
    patient_profile = PatientProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = (
            'id', 'email', 'first_name', 'last_name', 'phone_number',
            'role', 'is_verified', 'mfa_enabled', 'patient_profile',
            'created_at'
        )
        read_only_fields = ('id', 'role', 'is_verified', 'mfa_enabled', 'created_at')


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class MFASetupSerializer(serializers.Serializer):
    pass


class MFAVerifySerializer(serializers.Serializer):
    otp = serializers.CharField(max_length=6, min_length=6)
    temp_token = serializers.CharField(required=False)
