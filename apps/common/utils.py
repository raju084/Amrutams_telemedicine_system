import time
import logging
from contextlib import contextmanager
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import cache
from apps.common.middleware import get_current_correlation_id

logger = logging.getLogger(__name__)

def custom_exception_handler(exc, context):
    """
    Standardized API exception format across all endpoints.
    Always includes correlation_id for zero-friction tracing and debugging.
    """
    response = exception_handler(exc, context)
    correlation_id = get_current_correlation_id()

    if response is not None:
        custom_data = {
            'success': False,
            'error': {
                'code': getattr(exc, 'default_code', 'API_ERROR').upper(),
                'message': str(exc.detail) if hasattr(exc, 'detail') else str(exc),
                'details': response.data if isinstance(response.data, (dict, list)) else [str(response.data)],
            },
            'correlation_id': correlation_id,
        }
        response.data = custom_data
        return response

    # Unhandled 500 error
    logger.exception(f"Unhandled Server Error [Req: {correlation_id}]: {exc}")
    return Response({
        'success': False,
        'error': {
            'code': 'INTERNAL_SERVER_ERROR',
            'message': 'An internal error occurred. Please contact Amrutam Support.',
            'details': [str(exc)],
        },
        'correlation_id': correlation_id,
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@contextmanager
def distributed_lock(lock_key: str, timeout: int = 10, expire: int = 60):
    """
    Distributed locking pattern backed by Redis (or LocMemCache in dev)
    to prevent race conditions during high-concurrency doctor slot booking.
    """
    acquired = False
    start_time = time.time()
    lock_val = f"locked_{start_time}"

    try:
        while not acquired:
            # Use atomic cache.add which sets key only if not present
            acquired = cache.add(lock_key, lock_val, timeout=expire)
            if acquired:
                break
            if time.time() - start_time >= timeout:
                raise TimeoutError(f"Could not acquire distributed lock for {lock_key} within {timeout}s")
            time.sleep(0.05)
        yield
    finally:
        if acquired:
            # Release lock safely
            current_val = cache.get(lock_key)
            if current_val == lock_val:
                cache.delete(lock_key)
