from datetime import datetime, timedelta, time
from django.db import transaction
from django.db.models import Q
from rest_framework import generics, permissions, status, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, inline_serializer
from apps.doctors.models import Doctor, AvailabilitySlot
from apps.doctors.serializers import (
    DoctorListSerializer,
    DoctorDetailSerializer,
    AvailabilitySlotSerializer,
    SlotBatchCreateSerializer
)
from apps.common.permissions import IsDoctor

class DoctorListView(generics.ListAPIView):
    """
    Search and filter verified doctors by specialization, fee, experience, rating, or date availability.
    """
    serializer_class = DoctorListSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(tags=['Doctors & Availability'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Doctor.objects.filter(is_verified=True).select_related('user')
        specialization = self.request.query_params.get('specialization')
        max_fee = self.request.query_params.get('max_fee')
        min_experience = self.request.query_params.get('min_experience')
        min_rating = self.request.query_params.get('min_rating')
        date = self.request.query_params.get('date')
        search = self.request.query_params.get('search')

        if specialization:
            queryset = queryset.filter(specialization__iexact=specialization)
        if max_fee:
            queryset = queryset.filter(consultation_fee__lte=max_fee)
        if min_experience:
            queryset = queryset.filter(experience_years__gte=min_experience)
        if min_rating:
            queryset = queryset.filter(rating__gte=min_rating)
        if date:
            queryset = queryset.filter(slots__date=date, slots__status=AvailabilitySlot.STATUS_AVAILABLE).distinct()
        if search:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(qualification__icontains=search) |
                Q(bio__icontains=search)
            )
        return queryset.order_by('-rating', 'consultation_fee')


class DoctorDetailView(generics.RetrieveAPIView):
    """
    Retrieve public details of a specific doctor.
    """
    queryset = Doctor.objects.select_related('user')
    serializer_class = DoctorDetailSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(tags=['Doctors & Availability'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class DoctorSlotListView(generics.ListAPIView):
    """
    List available slots for a doctor on a specific date.
    """
    serializer_class = AvailabilitySlotSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(tags=['Doctors & Availability'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return AvailabilitySlot.objects.none()

        doctor_id = self.kwargs.get('doctor_id')
        date_str = self.request.query_params.get('date')

        queryset = AvailabilitySlot.objects.filter(
            doctor_id=doctor_id,
            status=AvailabilitySlot.STATUS_AVAILABLE
        ).select_related('doctor', 'doctor__user')

        if date_str:
            queryset = queryset.filter(date=date_str)
        return queryset.order_by('date', 'start_time')


class DoctorSlotBatchCreateView(APIView):
    """
    Allows an authenticated doctor to generate availability slots in bulk.
    """
    permission_classes = [permissions.IsAuthenticated, IsDoctor]

    @extend_schema(
        tags=['Doctors & Availability'],
        request=SlotBatchCreateSerializer,
        responses={
            201: inline_serializer(
                name='BatchCreateSlotResponse',
                fields={
                    'success': serializers.BooleanField(),
                    'message': serializers.CharField(),
                    'created_slots_count': serializers.IntegerField(),
                }
            )
        }
    )
    def post(self, request):
        serializer = SlotBatchCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        doctor = getattr(request.user, 'doctor_profile', None)
        if not doctor:
            return Response({'success': False, 'message': 'Doctor profile not found for this user.'}, status=status.HTTP_404_NOT_FOUND)

        date = serializer.validated_data['date']
        start_time = serializer.validated_data['start_time']
        end_time = serializer.validated_data['end_time']
        slot_duration = timedelta(minutes=serializer.validated_data['slot_duration_minutes'])

        curr_dt = datetime.combine(date, start_time)
        end_dt = datetime.combine(date, end_time)

        created_slots = []
        with transaction.atomic():
            while curr_dt + slot_duration <= end_dt:
                slot_start = curr_dt.time()
                slot_end = (curr_dt + slot_duration).time()

                slot, created = AvailabilitySlot.objects.get_or_create(
                    doctor=doctor,
                    date=date,
                    start_time=slot_start,
                    defaults={'end_time': slot_end, 'status': AvailabilitySlot.STATUS_AVAILABLE}
                )
                if created:
                    created_slots.append(slot)
                curr_dt += slot_duration

        return Response({
            'success': True,
            'message': f'Generated {len(created_slots)} new availability slots.',
            'created_slots_count': len(created_slots)
        }, status=status.HTTP_201_CREATED)
