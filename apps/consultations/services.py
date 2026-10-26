import uuid
import logging
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied
from apps.consultations.models import Consultation
from apps.doctors.models import AvailabilitySlot
from apps.common.utils import distributed_lock
from apps.common.middleware import CONSULTATION_BOOKINGS_TOTAL

logger = logging.getLogger(__name__)

class BookingService:
    """
    High-concurrency booking engine for Amrutam Telemedicine.
    Applies double-layered concurrency protection:
      1. Redis Distributed Lock (protecting cache & high-rate inbound bursts)
      2. PostgreSQL select_for_update() row-level pessimistic lock (strict ACID guarantee)
    """

    @classmethod
    def reserve_slot(cls, patient, slot_id, chief_complaint: str, symptoms: str = "") -> Consultation:
        """
        Step 1 in Booking Saga:
        Atomically reserves an available slot for a 10-minute checkout window.
        """
        lock_key = f"slot_reserve_lock_{slot_id}"

        with distributed_lock(lock_key, timeout=5):
            with transaction.atomic():
                # Acquire row-level lock on AvailabilitySlot
                try:
                    slot = AvailabilitySlot.objects.select_for_update().get(id=slot_id)
                except AvailabilitySlot.DoesNotExist:
                    raise ValidationError({'slot_id': 'Selected availability slot does not exist.'})

                # Check slot availability or expired lock
                if slot.status == AvailabilitySlot.STATUS_LOCKED:
                    if slot.is_lock_expired(timeout_seconds=600):
                        # Reclaim expired lock
                        slot.status = AvailabilitySlot.STATUS_AVAILABLE
                        slot.lock_token = None
                        slot.save(update_fields=['status', 'lock_token'])
                    else:
                        CONSULTATION_BOOKINGS_TOTAL.labels(status='conflict_locked').inc()
                        raise ValidationError({'slot_id': 'This slot is currently reserved by another patient. Please try again or choose another slot.'})

                if slot.status == AvailabilitySlot.STATUS_BOOKED:
                    CONSULTATION_BOOKINGS_TOTAL.labels(status='conflict_booked').inc()
                    raise ValidationError({'slot_id': 'This slot has already been booked.'})

                # Lock the slot for 10 minutes
                lock_token = uuid.uuid4()
                slot.status = AvailabilitySlot.STATUS_LOCKED
                slot.locked_at = timezone.now()
                slot.lock_token = lock_token
                slot.version += 1
                slot.save(update_fields=['status', 'locked_at', 'lock_token', 'version'])

                # Create Consultation in REQUESTED status
                consultation = Consultation(
                    patient=patient,
                    doctor=slot.doctor,
                    slot=slot,
                    status=Consultation.STATUS_REQUESTED,
                    chief_complaint=chief_complaint,
                )
                consultation.symptoms = symptoms
                consultation.save()

                CONSULTATION_BOOKINGS_TOTAL.labels(status='reserved').inc()
                logger.info("Slot %s reserved successfully for Patient %s. Consultation: %s",
                            slot_id, patient.id, consultation.id)
                return consultation

    @classmethod
    def confirm_consultation(cls, consultation_id, transaction_ref: str = None) -> Consultation:
        """
        Step 2 in Booking Saga (Called after successful payment verification):
        Transitions consultation to CONFIRMED and slot to BOOKED.
        """
        with transaction.atomic():
            consultation = Consultation.objects.select_for_update().select_related('slot').get(id=consultation_id)

            if consultation.status != Consultation.STATUS_REQUESTED:
                raise ValidationError({'status': f"Cannot confirm consultation in '{consultation.status}' status."})

            slot = consultation.slot
            slot.status = AvailabilitySlot.STATUS_BOOKED
            slot.lock_token = None
            slot.save(update_fields=['status', 'lock_token'])

            consultation.status = Consultation.STATUS_CONFIRMED
            consultation.video_room_id = f"amrutam-room-{uuid.uuid4().hex[:12]}"
            consultation.save(update_fields=['status', 'video_room_id'])

            CONSULTATION_BOOKINGS_TOTAL.labels(status='confirmed').inc()
            logger.info("Consultation %s confirmed. Video Room: %s",
                        consultation_id, consultation.video_room_id)

            # Fire domain signal for async notification dispatch (decoupled)
            try:
                from apps.notifications.signals import consultation_confirmed as confirmation_signal
                confirmation_signal.send(
                    sender=cls,
                    consultation_id=str(consultation_id),
                    payment_id=str(transaction_ref or ''),
                )
            except Exception as sig_exc:
                # Signal failure must never abort the booking transaction
                logger.warning("Notification signal failed (non-critical): %s", sig_exc)

            return consultation

    @classmethod
    def cancel_consultation(cls, consultation_id, requested_by_user, reason: str) -> Consultation:
        """
        Cancels consultation and safely releases slot back to AVAILABLE.
        """
        with transaction.atomic():
            consultation = Consultation.objects.select_for_update().select_related('slot', 'doctor__user').get(id=consultation_id)

            # Authorization check
            is_patient = (consultation.patient_id == requested_by_user.id)
            is_doctor = (consultation.doctor.user_id == requested_by_user.id)
            is_admin = (requested_by_user.role == 'ADMIN' or requested_by_user.is_staff)

            if not (is_patient or is_doctor or is_admin):
                raise PermissionDenied("You do not have permission to cancel this consultation.")

            if consultation.status in (Consultation.STATUS_COMPLETED, Consultation.STATUS_CANCELLED):
                raise ValidationError({'status': f"Cannot cancel consultation already in '{consultation.status}' state."})

            # Free the slot
            slot = consultation.slot
            slot.status = AvailabilitySlot.STATUS_AVAILABLE
            slot.locked_at = None
            slot.lock_token = None
            slot.save(update_fields=['status', 'locked_at', 'lock_token'])

            consultation.status = Consultation.STATUS_CANCELLED
            consultation.cancellation_reason = reason
            consultation.save(update_fields=['status', 'cancellation_reason'])

            CONSULTATION_BOOKINGS_TOTAL.labels(status='cancelled').inc()
            logger.info("Consultation %s cancelled by user %s. Slot %s released.",
                        consultation_id, requested_by_user.id, slot.id)

            # Fire domain signal for async notification dispatch (decoupled)
            try:
                from apps.notifications.signals import consultation_cancelled as cancel_signal
                cancel_signal.send(
                    sender=cls,
                    consultation_id=str(consultation_id),
                    reason=reason,
                    cancelled_by=str(requested_by_user.id),
                )
            except Exception as sig_exc:
                logger.warning("Cancellation notification signal failed (non-critical): %s", sig_exc)

            return consultation
