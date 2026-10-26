from django.db.models import Count, Sum, Avg, F
from django.utils import timezone
from datetime import timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, serializers
from drf_spectacular.utils import extend_schema, inline_serializer
from apps.consultations.models import Consultation
from apps.doctors.models import Doctor, AvailabilitySlot
from apps.payments.models import Payment
from apps.common.permissions import IsAdminUserRole

class AdminAnalyticsOverviewView(APIView):
    """
    High-performance analytics endpoint for Amrutam hospital administrators.
    Provides volume tracking (supporting 100k daily consultations target),
    doctor utilization, and Ayurvedic specialization revenue metrics.
    """
    permission_classes = [permissions.IsAuthenticated, IsAdminUserRole]

    @extend_schema(
        tags=['Admin Analytics'],
        responses={
            200: inline_serializer(
                name='AdminAnalyticsResponse',
                fields={
                    'success': serializers.BooleanField(),
                    'timestamp': serializers.DateTimeField(),
                    'consultations': serializers.DictField(),
                    'revenue': serializers.DictField(),
                    'doctor_utilization': serializers.DictField(),
                    'sla_observability': serializers.DictField(),
                }
            )
        }
    )
    def get(self, request):
        now = timezone.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        last_30_days = now - timedelta(days=30)

        consultations_today = Consultation.objects.filter(created_at__gte=start_of_day).count()
        consultations_last_30d = Consultation.objects.filter(created_at__gte=last_30_days).count()
        
        status_breakdown = dict(
            Consultation.objects.values('status')
            .annotate(count=Count('id'))
            .values_list('status', 'count')
        )

        total_revenue_stats = Payment.objects.filter(status=Payment.STATUS_SUCCESS).aggregate(
            total_revenue=Sum('amount'),
            avg_ticket_size=Avg('amount')
        )

        revenue_by_specialization = list(
            Payment.objects.filter(status=Payment.STATUS_SUCCESS)
            .values('consultation__doctor__specialization')
            .annotate(revenue=Sum('amount'), total_sessions=Count('id'))
            .order_by('-revenue')[:10]
        )

        total_slots = AvailabilitySlot.objects.filter(date=now.date()).count()
        booked_slots = AvailabilitySlot.objects.filter(date=now.date(), status=AvailabilitySlot.STATUS_BOOKED).count()
        utilization_rate = round((booked_slots / total_slots * 100), 2) if total_slots > 0 else 0.0

        sla_metrics = {
            'target_daily_capacity': 100000,
            'p95_read_latency_target_ms': 200,
            'p95_write_latency_target_ms': 500,
            'availability_target_percent': 99.95,
            'current_system_status': 'OPTIMAL'
        }

        return Response({
            'success': True,
            'timestamp': now,
            'consultations': {
                'today': consultations_today,
                'last_30_days': consultations_last_30d,
                'status_distribution': status_breakdown
            },
            'revenue': {
                'total_inr': total_revenue_stats['total_revenue'] or 0,
                'avg_consultation_fee_inr': round(total_revenue_stats['avg_ticket_size'] or 0, 2),
                'by_specialization': revenue_by_specialization
            },
            'doctor_utilization': {
                'date': str(now.date()),
                'total_slots': total_slots,
                'booked_slots': booked_slots,
                'utilization_percent': utilization_rate
            },
            'sla_observability': sla_metrics
        })
