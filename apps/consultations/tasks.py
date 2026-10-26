import logging
from celery import shared_task
from django.utils import timezone
from apps.doctors.models import AvailabilitySlot
from apps.consultations.models import Consultation

logger = logging.getLogger(__name__)

@shared_task(name='apps.consultations.tasks.release_expired_slots_task')
def release_expired_slots_task():
    """
    Periodic Celery Beat task:
    Reclaims slots locked in checkout older than 10 minutes and cancels pending consultations.
    """
    now = timezone.now()
    expired_slots = AvailabilitySlot.objects.filter(
        status=AvailabilitySlot.STATUS_LOCKED,
        locked_at__lte=now - timezone.timedelta(minutes=10)
    )

    reclaimed_count = 0
    for slot in expired_slots:
        slot.status = AvailabilitySlot.STATUS_AVAILABLE
        slot.locked_at = None
        slot.lock_token = None
        slot.save(update_fields=['status', 'locked_at', 'lock_token'])

        # Cancel associated consultation if still in REQUESTED status
        Consultation.objects.filter(
            slot=slot,
            status=Consultation.STATUS_REQUESTED
        ).update(
            status=Consultation.STATUS_CANCELLED,
            cancellation_reason="Auto-cancelled due to payment timeout (10 min expiration)."
        )
        reclaimed_count += 1

    if reclaimed_count > 0:
        logger.info(f"Reclaimed {reclaimed_count} expired consultation slots.")
    return reclaimed_count


@shared_task(name='apps.consultations.tasks.daily_analytics_rollup_task')
def daily_analytics_rollup_task():
    """
    Periodic task: generates daily operational statistics.
    """
    today = timezone.now().date()
    total_today = Consultation.objects.filter(created_at__date=today).count()
    completed_today = Consultation.objects.filter(created_at__date=today, status=Consultation.STATUS_COMPLETED).count()
    cancelled_today = Consultation.objects.filter(created_at__date=today, status=Consultation.STATUS_CANCELLED).count()

    logger.info(f"Daily Rollup for {today}: Total={total_today}, Completed={completed_today}, Cancelled={cancelled_today}")
    return {
        'date': str(today),
        'total': total_today,
        'completed': completed_today,
        'cancelled': cancelled_today
    }
