import json
import time
import uuid
import logging
import hashlib
from datetime import timedelta
from django.utils import timezone
from django.http import JsonResponse
from apps.common.logging import get_current_correlation_id, set_current_correlation_id
from prometheus_client import Counter, Histogram

logger = logging.getLogger(__name__)

# Prometheus Metrics Definitions
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    'telemedicine_http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint', 'status_code'],
    buckets=(0.025, 0.05, 0.1, 0.2, 0.3, 0.5, 1.0, 2.5, 5.0)
)
HTTP_REQUESTS_TOTAL = Counter(
    'telemedicine_http_requests_total',
    'Total count of HTTP requests processed',
    ['method', 'endpoint', 'status_code']
)
CONSULTATION_BOOKINGS_TOTAL = Counter(
    'telemedicine_consultation_bookings_total',
    'Total consultation booking attempts',
    ['status']
)
IDEMPOTENCY_HITS_TOTAL = Counter(
    'telemedicine_idempotency_hits_total',
    'Total cached responses served from idempotency store',
    ['status']
)

class RequestCorrelationIdMiddleware:
    """
    Assigns or preserves X-Correlation-Id for distributed tracing across services.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        correlation_id = request.headers.get('X-Correlation-Id') or str(uuid.uuid4())
        set_current_correlation_id(correlation_id)
        request.correlation_id = correlation_id

        response = self.get_response(request)
        response['X-Correlation-Id'] = correlation_id
        return response


class MetricsCollectionMiddleware:
    """
    Instruments every HTTP request with high-resolution Prometheus histograms & counters.
    Enables tracking of p95 <200ms read and <500ms write requirements.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.perf_counter()
        response = self.get_response(request)
        duration = time.perf_counter() - start_time

        path = request.path
        if path.startswith('/api/v1/'):
            parts = path.strip('/').split('/')
            endpoint = f"/{parts[0]}/{parts[1]}/{parts[2]}" if len(parts) >= 3 else path
        else:
            endpoint = path

        method = request.method
        status_code = str(response.status_code)

        try:
            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=method,
                endpoint=endpoint,
                status_code=status_code
            ).observe(duration)

            HTTP_REQUESTS_TOTAL.labels(
                method=method,
                endpoint=endpoint,
                status_code=status_code
            ).inc()
        except Exception as e:
            logger.debug(f"Metrics recording ignored: {e}")

        return response


class IdempotencyMiddleware:
    """
    Guarantees exactly-once write semantics for financial, booking, and prescription transactions.
    Clients supply an `Idempotency-Key` header on POST / PATCH / PUT requests.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method not in ('POST', 'PUT', 'PATCH'):
            return self.get_response(request)

        idempotency_key = request.headers.get('Idempotency-Key') or request.headers.get('idempotency-key') or request.META.get('HTTP_IDEMPOTENCY_KEY')
        if not idempotency_key:
            return self.get_response(request)

        from apps.common.models import IdempotencyRecord

        body_bytes = request.body
        request_hash = hashlib.sha256(body_bytes).hexdigest()
        user_id = getattr(request.user, 'id', None) if request.user.is_authenticated else None

        record = IdempotencyRecord.objects.filter(key=idempotency_key).first()

        if record:
            if record.is_expired():
                record.delete()
            elif record.status == IdempotencyRecord.STATUS_PENDING:
                return JsonResponse({
                    'success': False,
                    'error': {
                        'code': 'CONCURRENT_REQUEST',
                        'message': 'A duplicate request with this Idempotency-Key is currently being processed.'
                    }
                }, status=409)
            elif record.status == IdempotencyRecord.STATUS_COMPLETED:
                IDEMPOTENCY_HITS_TOTAL.labels(status='cache_hit').inc()
                cached_response = JsonResponse(record.response_body, status=record.response_code)
                cached_response['X-Cache-Lookup'] = 'HIT - Idempotency'
                cached_response['Idempotency-Key'] = idempotency_key
                return cached_response

        new_record = IdempotencyRecord.objects.create(
            key=idempotency_key,
            user_id=user_id,
            request_path=request.path,
            request_method=request.method,
            request_hash=request_hash,
            status=IdempotencyRecord.STATUS_PENDING,
            expires_at=timezone.now() + timedelta(hours=24)
        )

        try:
            response = self.get_response(request)
            
            if 200 <= response.status_code < 300:
                try:
                    body_json = json.loads(response.content.decode('utf-8'))
                except Exception:
                    body_json = getattr(response, 'data', None)

                new_record.status = IdempotencyRecord.STATUS_COMPLETED
                new_record.response_code = response.status_code
                new_record.response_body = body_json
                new_record.save(update_fields=['status', 'response_code', 'response_body'])
            elif response.status_code >= 400:
                new_record.status = IdempotencyRecord.STATUS_FAILED
                new_record.response_code = response.status_code
                new_record.save(update_fields=['status', 'response_code'])

            response['Idempotency-Key'] = idempotency_key
            return response
        except Exception as exc:
            new_record.status = IdempotencyRecord.STATUS_FAILED
            new_record.save(update_fields=['status'])
            raise exc
