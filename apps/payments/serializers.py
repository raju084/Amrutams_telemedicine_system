from rest_framework import serializers
from apps.payments.models import Payment

class PaymentInitiateSerializer(serializers.Serializer):
    consultation_id = serializers.UUIDField()


class PaymentDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = (
            'id', 'consultation_id', 'amount', 'currency',
            'status', 'gateway_order_id', 'gateway_payment_id',
            'idempotency_key', 'created_at'
        )


class PaymentWebhookSerializer(serializers.Serializer):
    event = serializers.CharField()
    order_id = serializers.CharField()
    payment_id = serializers.CharField()
