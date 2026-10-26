"""
Razorpay HMAC-SHA256 Webhook Signature Verification.

This module provides tamper-proof webhook authentication by verifying that
every incoming webhook payload from Razorpay was genuinely signed with the
shared webhook secret. Forged or replayed webhooks that fail HMAC verification
are rejected with HTTP 400 before any business logic is executed.

References:
    https://razorpay.com/docs/webhooks/validate-test/
"""

import hmac
import hashlib
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class WebhookSignatureError(Exception):
    """Raised when a webhook payload fails HMAC signature verification."""
    pass


def verify_razorpay_webhook_signature(request_body: bytes, signature_header: str) -> bool:
    """
    Verify a Razorpay webhook HMAC-SHA256 signature.

    Args:
        request_body: Raw bytes of the request body (NOT decoded — HMAC is over raw bytes).
        signature_header: Value of the 'X-Razorpay-Signature' header.

    Returns:
        True if signature is valid.

    Raises:
        WebhookSignatureError: If signature is missing, malformed, or does not match.
    """
    webhook_secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', None)

    if not webhook_secret:
        # In non-production environments without a secret configured, skip verification.
        # This allows local dev/test to proceed without real Razorpay credentials.
        if getattr(settings, 'DEBUG', False):
            logger.warning(
                "RAZORPAY_WEBHOOK_SECRET is not configured — skipping HMAC verification (DEBUG mode)."
            )
            return True
        else:
            raise WebhookSignatureError(
                "RAZORPAY_WEBHOOK_SECRET is not configured. "
                "Cannot verify webhook authenticity in production."
            )

    if not signature_header:
        raise WebhookSignatureError(
            "Missing 'X-Razorpay-Signature' header. Webhook rejected."
        )

    # Compute expected HMAC using shared webhook secret
    expected_signature = hmac.new(
        webhook_secret.encode('utf-8'),
        request_body,
        hashlib.sha256
    ).hexdigest()

    # Use constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(expected_signature, signature_header):
        logger.warning(
            "Razorpay webhook HMAC verification failed. "
            "Possible tampering or wrong webhook secret."
        )
        raise WebhookSignatureError(
            "Webhook signature mismatch. Request rejected."
        )

    logger.debug("Razorpay webhook signature verified successfully.")
    return True
