import logging
import threading

_thread_locals = threading.local()

def get_current_correlation_id():
    return getattr(_thread_locals, 'correlation_id', None)

def set_current_correlation_id(correlation_id):
    _thread_locals.correlation_id = correlation_id

class CorrelationIdFilter(logging.Filter):
    """
    Injects correlation_id into all log records for end-to-end tracing.
    """
    def filter(self, record):
        record.correlation_id = get_current_correlation_id() or 'no-trace'
        return True
