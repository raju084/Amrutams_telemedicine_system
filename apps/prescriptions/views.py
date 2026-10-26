from django.db import transaction
from django.utils import timezone
from rest_framework import generics, permissions, status, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, inline_serializer
from apps.prescriptions.models import Prescription, PrescriptionItem
from apps.prescriptions.serializers import (
    PrescriptionCreateSerializer,
    PrescriptionDetailSerializer,
)
from apps.consultations.models import Consultation
from apps.common.permissions import IsDoctor, IsOwnerOrDoctorOrAdmin
from apps.common.crypto import generate_prescription_signature, verify_prescription_signature

class PrescriptionCreateView(APIView):
    """
    Allows the consulting doctor to create and cryptographically sign a digital prescription.
    """
    permission_classes = [permissions.IsAuthenticated, IsDoctor]

    @extend_schema(
        tags=['Prescriptions'],
        request=PrescriptionCreateSerializer,
        responses={
            201: inline_serializer(
                name='PrescriptionCreatedResponse',
                fields={
                    'success': serializers.BooleanField(),
                    'message': serializers.CharField(),
                    'prescription': PrescriptionDetailSerializer(),
                }
            )
        }
    )
    def post(self, request):
        serializer = PrescriptionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        consultation = serializer.validated_data['consultation']
        doctor = getattr(request.user, 'doctor_profile', None)

        if not doctor or consultation.doctor_id != doctor.id:
            return Response({
                'success': False,
                'message': 'Only the assigned consulting doctor can issue a prescription for this session.'
            }, status=status.HTTP_403_FORBIDDEN)

        items_data = serializer.validated_data.pop('items')

        with transaction.atomic():
            prescription = Prescription.objects.create(
                consultation=consultation,
                diagnosis=serializer.validated_data['diagnosis'],
                dietary_advice=serializer.validated_data.get('dietary_advice', ''),
                lifestyle_recommendations=serializer.validated_data.get('lifestyle_recommendations', ''),
                follow_up_date=serializer.validated_data.get('follow_up_date')
            )

            created_items = []
            for item in items_data:
                p_item = PrescriptionItem.objects.create(prescription=prescription, **item)
                created_items.append({
                    'medicine_name': p_item.medicine_name,
                    'dosage': p_item.dosage,
                    'frequency': p_item.frequency,
                    'duration_days': p_item.duration_days,
                })

            # Sort canonically by medicine_name
            created_items.sort(key=lambda x: x['medicine_name'])

            sig_payload = {
                'prescription_id': str(prescription.id),
                'consultation_id': str(consultation.id),
                'doctor_id': str(doctor.id),
                'patient_id': str(consultation.patient_id),
                'diagnosis': prescription.diagnosis,
                'items': created_items,
            }
            signature = generate_prescription_signature(sig_payload, doctor.digital_signature_key)
            prescription.digital_signature = signature
            prescription.signature_timestamp = timezone.now()
            prescription.save(update_fields=['digital_signature', 'signature_timestamp'])

        return Response({
            'success': True,
            'message': 'Prescription issued and cryptographically signed successfully.',
            'prescription': PrescriptionDetailSerializer(prescription).data
        }, status=status.HTTP_201_CREATED)


class PrescriptionDetailView(generics.RetrieveAPIView):
    """
    Retrieve prescription by ID.
    """
    queryset = Prescription.objects.select_related(
        'consultation', 'consultation__doctor', 'consultation__doctor__user', 'consultation__patient'
    ).prefetch_related('items')
    serializer_class = PrescriptionDetailSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrDoctorOrAdmin]

    @extend_schema(tags=['Prescriptions'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class PrescriptionVerifySignatureView(APIView):
    """
    Public / Pharmacy verification endpoint:
    Verifies that the prescription was indeed signed by the licensed doctor and has not been altered.
    """
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Prescriptions'],
        responses={
            200: inline_serializer(
                name='PrescriptionSignatureVerification',
                fields={
                    'success': serializers.BooleanField(),
                    'prescription_id': serializers.CharField(),
                    'doctor_name': serializers.CharField(),
                    'doctor_license': serializers.CharField(),
                    'signature_valid': serializers.BooleanField(),
                    'signed_at': serializers.DateTimeField(),
                    'status': serializers.CharField(),
                }
            )
        }
    )
    def get(self, request, pk):
        try:
            prescription = Prescription.objects.select_related('consultation__doctor').prefetch_related('items').get(pk=pk)
        except Prescription.DoesNotExist:
            return Response({'success': False, 'message': 'Prescription not found.'}, status=status.HTTP_404_NOT_FOUND)

        doctor = prescription.consultation.doctor
        items_payload = [
            {
                'medicine_name': item.medicine_name,
                'dosage': item.dosage,
                'frequency': item.frequency,
                'duration_days': item.duration_days,
            }
            for item in prescription.items.all()
        ]
        items_payload.sort(key=lambda x: x['medicine_name'])
        sig_payload = {
            'prescription_id': str(prescription.id),
            'consultation_id': str(prescription.consultation_id),
            'doctor_id': str(doctor.id),
            'patient_id': str(prescription.consultation.patient_id),
            'diagnosis': prescription.diagnosis,
            'items': items_payload,
        }

        is_valid = verify_prescription_signature(
            sig_payload,
            doctor.digital_signature_key,
            prescription.digital_signature
        )

        return Response({
            'success': True,
            'prescription_id': str(prescription.id),
            'doctor_name': doctor.user.get_full_name(),
            'doctor_license': doctor.license_number,
            'signature_valid': is_valid,
            'signed_at': prescription.signature_timestamp,
            'status': 'AUTHENTIC & VERIFIED' if is_valid else 'TAMPERED OR INVALID SIGNATURE'
        })
