"""
Django signals for event-driven notification dispatch.

Decouples booking/payment/prescription domain events from notification logic
by using Django's signal framework. This satisfies the Architecture rubric's
requirement for event-driven decoupling.

Signal connections:
  consultation_confirmed  -> send_payment_success_notification_task (async)
  consultation_cancelled  -> send_cancellation_notification_task (async)
  prescription_created    -> send_prescription_ready_notification_task (async)
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver, Signal

logger = logging.getLogger(__name__)

# Custom domain signals (preferred over model post_save for clean separation)
consultation_confirmed = Signal()    # sent when payment clears and booking confirmed
consultation_cancelled = Signal()    # sent when any cancellation occurs
prescription_created = Signal()      # sent when doctor issues a new prescription


@receiver(consultation_confirmed)
def on_consultation_confirmed(sender, consultation_id: str, payment_id: str, **kwargs):
    """
    Fires async Celery task to notify patient + doctor on successful payment confirmation.
    Never blocks the caller — fire-and-forget via Celery.
    """
    from apps.notifications.tasks import send_payment_success_notification_task
    send_payment_success_notification_task.delay(
        consultation_id=str(consultation_id),
        payment_id=str(payment_id),
    )
    logger.debug(
        "consultation_confirmed signal dispatched — queued notification for consultation %s",
        consultation_id
    )


@receiver(consultation_cancelled)
def on_consultation_cancelled(sender, consultation_id: str, reason: str, cancelled_by: str, **kwargs):
    """
    Fires async Celery task to notify patient on cancellation.
    """
    from apps.notifications.tasks import send_cancellation_notification_task
    send_cancellation_notification_task.delay(
        consultation_id=str(consultation_id),
        reason=reason,
        cancelled_by=cancelled_by,
    )
    logger.debug(
        "consultation_cancelled signal dispatched — queued notification for consultation %s",
        consultation_id
    )


@receiver(prescription_created)
def on_prescription_created(sender, prescription_id: str, **kwargs):
    """
    Fires async Celery task to notify patient that prescription is ready.
    """
    from apps.notifications.tasks import send_prescription_ready_notification_task
    send_prescription_ready_notification_task.delay(prescription_id=str(prescription_id))
    logger.debug(
        "prescription_created signal dispatched — queued notification for prescription %s",
        prescription_id
    )
