import uuid
from django.utils import timezone
from rest_framework import generics, permissions, status, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, inline_serializer
from apps.consultations.models import Consultation
from apps.consultations.serializers import (
    ConsultationCreateSerializer,
    ConsultationDetailSerializer,
    ConsultationStatusTransitionSerializer,
)
from apps.consultations.services import BookingService
from apps.common.permissions import IsPatient, IsOwnerOrDoctorOrAdmin

class ConsultationCreateView(APIView):
    """
    Reserve an availability slot and initiate a consultation booking.
    Protected with Idempotency-Key support and concurrency locking.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=['Consultations Lifecycle'],
        request=ConsultationCreateSerializer,
        responses={
            201: inline_serializer(
                name='ConsultationBookResponse',
                fields={
                    'success': serializers.BooleanField(),
                    'message': serializers.CharField(),
                    'consultation': ConsultationDetailSerializer()
                }
            )
        }
    )
    def post(self, request):
        serializer = ConsultationCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        slot_id = serializer.validated_data['slot_id']
        chief_complaint = serializer.validated_data['chief_complaint']
        symptoms = serializer.validated_data.get('symptoms', '')

        consultation = BookingService.reserve_slot(
            patient=request.user,
            slot_id=slot_id,
            chief_complaint=chief_complaint,
            symptoms=symptoms
        )

        return Response({
            'success': True,
            'message': 'Slot reserved successfully for 10 minutes. Please complete payment to confirm booking.',
            'consultation': ConsultationDetailSerializer(consultation).data
        }, status=status.HTTP_201_CREATED)


class ConsultationListView(generics.ListAPIView):
    """
    List consultations for the authenticated user (Patient sees theirs, Doctor sees theirs, Admin sees all).
    """
    serializer_class = ConsultationDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=['Consultations Lifecycle'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Consultation.objects.none()

        user = self.request.user
        if not user or not user.is_authenticated:
            return Consultation.objects.none()

        if user.role == 'ADMIN' or user.is_staff:
            return Consultation.objects.all().select_related('patient', 'doctor', 'doctor__user', 'slot')
        elif user.role == 'DOCTOR' and hasattr(user, 'doctor_profile'):
            return Consultation.objects.filter(doctor=user.doctor_profile).select_related('patient', 'doctor', 'doctor__user', 'slot')
        else:
            return Consultation.objects.filter(patient=user).select_related('patient', 'doctor', 'doctor__user', 'slot')


class ConsultationDetailView(generics.RetrieveAPIView):
    """
    Retrieve single consultation details.
    """
    queryset = Consultation.objects.select_related('patient', 'doctor', 'doctor__user', 'slot')
    serializer_class = ConsultationDetailSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrDoctorOrAdmin]

    @extend_schema(tags=['Consultations Lifecycle'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ConsultationTransitionView(APIView):
    """
    State machine transition handler:
    - START: Doctor begins the live video call (transitions to IN_PROGRESS)
    - COMPLETE: Doctor ends the consultation (transitions to COMPLETED)
    - CANCEL: Patient or Doctor cancels (frees the slot)
    - NO_SHOW: Doctor marks patient absent
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=['Consultations Lifecycle'],
        request=ConsultationStatusTransitionSerializer,
        responses={
            200: inline_serializer(
                name='ConsultationTransitionResponse',
                fields={
                    'success': serializers.BooleanField(),
                    'message': serializers.CharField(),
                    'consultation': ConsultationDetailSerializer()
                }
            )
        }
    )
    def post(self, request, pk):
        serializer = ConsultationStatusTransitionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        action = serializer.validated_data['action']
        reason = serializer.validated_data.get('reason', '')

        try:
            consultation = Consultation.objects.select_related('doctor__user', 'slot').get(pk=pk)
        except Consultation.DoesNotExist:
            return Response({'success': False, 'message': 'Consultation not found.'}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        is_doctor = (consultation.doctor.user_id == user.id)
        is_patient = (consultation.patient_id == user.id)
        is_admin = (user.role == 'ADMIN' or user.is_staff)

        if action == 'START':
            if not (is_doctor or is_admin):
                return Response({'success': False, 'message': 'Only the consulting doctor can start the session.'}, status=status.HTTP_403_FORBIDDEN)
            if consultation.status != Consultation.STATUS_CONFIRMED:
                return Response({'success': False, 'message': f'Cannot start consultation in {consultation.status} state.'}, status=status.HTTP_400_BAD_REQUEST)
            consultation.status = Consultation.STATUS_IN_PROGRESS
            consultation.started_at = timezone.now()
            consultation.save(update_fields=['status', 'started_at'])

        elif action == 'COMPLETE':
            if not (is_doctor or is_admin):
                return Response({'success': False, 'message': 'Only the consulting doctor can complete the session.'}, status=status.HTTP_403_FORBIDDEN)
            if consultation.status != Consultation.STATUS_IN_PROGRESS:
                return Response({'success': False, 'message': f'Cannot complete consultation that is not in progress.'}, status=status.HTTP_400_BAD_REQUEST)
            consultation.status = Consultation.STATUS_COMPLETED
            consultation.ended_at = timezone.now()
            consultation.save(update_fields=['status', 'ended_at'])

        elif action == 'CANCEL':
            BookingService.cancel_consultation(consultation.id, user, reason or "Cancelled by user request")
            consultation.refresh_from_db()

        elif action == 'NO_SHOW':
            if not (is_doctor or is_admin):
                return Response({'success': False, 'message': 'Only doctor or admin can mark no-show.'}, status=status.HTTP_403_FORBIDDEN)
            consultation.status = Consultation.STATUS_NO_SHOW
            consultation.cancellation_reason = reason or "Patient did not attend."
            consultation.save(update_fields=['status', 'cancellation_reason'])

        return Response({
            'success': True,
            'message': f"Consultation status transitioned to {consultation.status}.",
            'consultation': ConsultationDetailSerializer(consultation).data
        })


class ConsultationVideoTokenView(APIView):
    """
    Returns WebRTC / Agora video credentials for the consultation room.
    """
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrDoctorOrAdmin]

    @extend_schema(
        tags=['Consultations Lifecycle'],
        responses={
            200: inline_serializer(
                name='VideoTokenResponse',
                fields={
                    'success': serializers.BooleanField(),
                    'room_id': serializers.CharField(),
                    'user_id': serializers.CharField(),
                    'role': serializers.CharField(),
                    'token': serializers.CharField(),
                    'expires_in_seconds': serializers.IntegerField(),
                }
            )
        }
    )
    def get(self, request, pk):
        try:
            consultation = Consultation.objects.get(pk=pk)
        except Consultation.DoesNotExist:
            return Response({'success': False, 'message': 'Consultation not found.'}, status=status.HTTP_404_NOT_FOUND)

        self.check_object_permissions(request, consultation)

        if consultation.status not in (Consultation.STATUS_CONFIRMED, Consultation.STATUS_IN_PROGRESS):
            return Response({
                'success': False,
                'message': f'Video room is not active for consultation in {consultation.status} state.'
            }, status=status.HTTP_400_BAD_REQUEST)

        role_str = 'publisher' if request.user.role == 'DOCTOR' else 'subscriber'
        return Response({
            'success': True,
            'room_id': consultation.video_room_id,
            'user_id': str(request.user.id),
            'role': role_str,
            'token': f"vtoken_{uuid.uuid4().hex}_{int(timezone.now().timestamp())}",
            'expires_in_seconds': 3600
        })
