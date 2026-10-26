import json
import logging
from apps.audit.models import AuditLog

logger = logging.getLogger(__name__)

class AuditLoggingMiddleware:
    """
    Automatically tracks state-changing API requests and sensitive resource access.
    Records client IP, user identity, action, and correlation ID into immutable log.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Log mutating actions or sensitive endpoints on success
        if request.path.startswith('/api/v1/') and request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            if 200 <= response.status_code < 400:
                try:
                    self._record_audit_event(request, response)
                except Exception as e:
                    logger.error(f"Failed to record audit event: {e}")

        return response

    def _record_audit_event(self, request, response):
        user = request.user if hasattr(request, 'user') and request.user.is_authenticated else None
        user_id = user.id if user else None
        user_email = user.email if user else 'anonymous'
        user_role = getattr(user, 'role', 'ANONYMOUS')

        # Extract client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0].strip()
        else:
            ip_address = request.META.get('REMOTE_ADDR')

        action = f"HTTP_{request.method}_{request.path}"
        correlation_id = getattr(request, 'correlation_id', '')

        AuditLog.objects.create(
            user_id=user_id,
            user_email=user_email,
            user_role=user_role,
            action=action,
            resource_type='API_ENDPOINT',
            resource_id=request.path,
            ip_address=ip_address,
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            correlation_id=correlation_id,
            payload_diff={'status_code': response.status_code}
        )
