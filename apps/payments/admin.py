from django.contrib import admin
from apps.payments.models import Payment

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'consultation', 'amount', 'currency', 'status', 'gateway_order_id', 'created_at')
    list_filter = ('status', 'currency')
    search_fields = ('gateway_order_id', 'gateway_payment_id', 'idempotency_key')
