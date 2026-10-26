import uuid
import logging
from django.conf import settings
from rest_framework import permissions, status, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, inline_serializer
from apps.payments.models import Payment
from apps.payments.serializers import (
    PaymentInitiateSerializer,
    PaymentDetailSerializer,
    PaymentWebhookSerializer,
)
from apps.payments.services import PaymentService

logger = logging.getLogger(__name__)


class PaymentInitiateView(APIView):
    """
    Initiate checkout payment for a reserved consultation.
    Requires or generates an Idempotency-Key.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=['Payments & Billing'],
        request=PaymentInitiateSerializer,
        responses={
            201: inline_serializer(
                name='PaymentInitiateResponse',
                fields={
                    'success': serializers.BooleanField(),
                    'message': serializers.CharField(),
                    'payment': PaymentDetailSerializer(),
                    'gateway_checkout_data': serializers.DictField(),
                }
            )
        }
    )
    def post(self, request):
        serializer = PaymentInitiateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        consultation_id = serializer.validated_data['consultation_id']
        idempotency_key = (
            request.headers.get('Idempotency-Key')
            or f"pay_key_{consultation_id}_{uuid.uuid4().hex[:8]}"
        )

        payment = PaymentService.initiate_payment(
            consultation_id=consultation_id,
            idempotency_key=idempotency_key
        )

        return Response({
            'success': True,
            'message': 'Payment intent created.',
            'payment': PaymentDetailSerializer(payment).data,
            'gateway_checkout_data': {
                'order_id': payment.gateway_order_id,
                'amount_paise': int(payment.amount * 100),
                'currency': payment.currency,
                'key_id': settings.RAZORPAY_KEY_ID
            }
        }, status=status.HTTP_201_CREATED)


class PaymentWebhookView(APIView):
    """
    Asynchronous payment webhook from Payment Gateway (Razorpay/Stripe).

    Security:
        - Verifies Razorpay HMAC-SHA256 signature via X-Razorpay-Signature header
          before processing any payload to prevent forged webhook attacks.
        - AllowAny is intentional (public endpoint) — authentication is via HMAC, not JWT.
        - Idempotent: repeated webhooks for the same payment are no-ops.
    """
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Payments & Billing'],
        request=PaymentWebhookSerializer,
        responses={
            200: inline_serializer(
                name='WebhookResponse',
                fields={
                    'success': serializers.BooleanField(),
                    'payment_status': serializers.CharField(required=False),
                    'message': serializers.CharField(required=False),
                }
            )
        }
    )
    def post(self, request):
        from apps.payments.webhook_verification import (
            verify_razorpay_webhook_signature,
            WebhookSignatureError,
        )

        # Step 1: Verify HMAC-SHA256 signature BEFORE deserializing payload.
        # This rejects forged or tampered webhooks before any DB access.
        raw_body = request.body  # DRF has already buffered this
        razorpay_signature = request.headers.get('X-Razorpay-Signature', '')

        try:
            verify_razorpay_webhook_signature(raw_body, razorpay_signature)
        except WebhookSignatureError as exc:
            logger.warning(
                "Webhook rejected — HMAC verification failed. "
                "correlation_id=%s reason=%s",
                getattr(request, 'correlation_id', 'none'),
                str(exc)
            )
            return Response(
                {'success': False, 'error': str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Step 2: Validate payload schema
        serializer = PaymentWebhookSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        event = serializer.validated_data['event']
        order_id = serializer.validated_data['order_id']
        payment_id = serializer.validated_data['payment_id']

        # Step 3: Process known events idempotently
        if event in ('payment.captured', 'charge.successful'):
            payment = PaymentService.handle_payment_success(
                gateway_order_id=order_id,
                gateway_payment_id=payment_id
            )
            logger.info(
                "Webhook processed: event=%s order_id=%s payment_id=%s status=%s",
                event, order_id, payment_id, payment.status
            )
            return Response({'success': True, 'payment_status': payment.status})

        logger.info("Webhook: unhandled event=%s — acknowledged.", event)
        return Response({'success': True, 'message': f'Unhandled event {event} ignored'})


class PaymentDetailView(APIView):
    """
    Retrieve payment status by payment ID.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=['Payments & Billing'],
        responses={
            200: inline_serializer(
                name='PaymentStatusResponse',
                fields={
                    'success': serializers.BooleanField(),
                    'payment': PaymentDetailSerializer(),
                }
            )
        }
    )
    def get(self, request, pk):
        try:
            payment = Payment.objects.select_related('consultation__patient').get(pk=pk)
        except Payment.DoesNotExist:
            return Response(
                {'success': False, 'message': 'Payment record not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Ownership check: only the patient who made the payment or staff may view it
        is_owner = (
            hasattr(payment, 'consultation')
            and payment.consultation.patient_id == request.user.id
        )
        if not is_owner and not (request.user.is_staff or getattr(request.user, 'role', '') == 'ADMIN'):
            return Response(
                {'success': False, 'message': 'You do not have permission to view this payment.'},
                status=status.HTTP_403_FORBIDDEN
            )

        return Response({
            'success': True,
            'payment': PaymentDetailSerializer(payment).data
        })
