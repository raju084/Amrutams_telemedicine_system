import uuid
import logging
from django.db import transaction
from rest_framework.exceptions import ValidationError
from apps.payments.models import Payment
from apps.consultations.models import Consultation
from apps.consultations.services import BookingService

logger = logging.getLogger(__name__)

class PaymentService:
    """
    Manages payment lifecycles and coordinates Saga state transitions between
    Payment and Consultation services.
    """

    @classmethod
    def initiate_payment(cls, consultation_id, idempotency_key: str) -> Payment:
        """
        Creates an idempotent payment record and mock gateway order.
        """
        existing = Payment.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing

        with transaction.atomic():
            consultation = Consultation.objects.select_for_update().select_related('doctor').get(id=consultation_id)

            if consultation.status != Consultation.STATUS_REQUESTED:
                raise ValidationError({'consultation': f"Cannot initiate payment for consultation in status '{consultation.status}'."})

            amount = consultation.doctor.consultation_fee
            gateway_order_id = f"order_{uuid.uuid4().hex[:14]}"

            payment = Payment.objects.create(
                consultation=consultation,
                amount=amount,
                currency='INR',
                status=Payment.STATUS_PENDING,
                gateway_order_id=gateway_order_id,
                idempotency_key=idempotency_key,
                gateway_response={'order_created_at': str(uuid.uuid1())}
            )
            return payment

    @classmethod
    def handle_payment_success(cls, gateway_order_id: str, gateway_payment_id: str) -> Payment:
        """
        Idempotent payment success processor (called via webhook or callback).
        Advances Saga to confirm consultation.
        """
        with transaction.atomic():
            payment = Payment.objects.select_for_update().select_related('consultation').get(gateway_order_id=gateway_order_id)

            if payment.status == Payment.STATUS_SUCCESS:
                # Already processed (idempotent no-op)
                return payment

            payment.status = Payment.STATUS_SUCCESS
            payment.gateway_payment_id = gateway_payment_id
            payment.save(update_fields=['status', 'gateway_payment_id'])

            # Saga step: Confirm Consultation
            BookingService.confirm_consultation(
                consultation_id=payment.consultation_id,
                transaction_ref=gateway_payment_id
            )

            logger.info(f"Payment {payment.id} succeeded. Consultation {payment.consultation_id} confirmed.")
            return payment

    @classmethod
    def refund_payment(cls, consultation_id: str, reason: str = "Consultation cancelled") -> Payment:
        """
        Compensating Saga transaction: refunds payment if consultation is cancelled.
        """
        with transaction.atomic():
            payment = Payment.objects.select_for_update().filter(
                consultation_id=consultation_id,
                status=Payment.STATUS_SUCCESS
            ).first()

            if not payment:
                return None

            payment.status = Payment.STATUS_REFUNDED
            payment.gateway_response['refund_reason'] = reason
            payment.save(update_fields=['status', 'gateway_response'])

            logger.info(f"Payment {payment.id} refunded for consultation {consultation_id}. Reason: {reason}")
            return payment
