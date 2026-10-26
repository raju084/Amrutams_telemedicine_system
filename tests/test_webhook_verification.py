"""
Tests for Razorpay webhook HMAC signature verification.

Validates that:
  - Valid HMAC signatures are accepted
  - Tampered signatures are rejected with WebhookSignatureError
  - Missing signatures are rejected
  - The PaymentWebhookView properly rejects unverified webhooks (HTTP 400)
  - Timing-safe comparison prevents timing attacks

Run with: pytest tests/test_webhook_verification.py -v
"""

import hmac
import hashlib
import json
import pytest
from unittest.mock import patch
from django.test import TestCase, RequestFactory
from django.urls import reverse
from apps.payments.webhook_verification import (
    verify_razorpay_webhook_signature,
    WebhookSignatureError,
)


VALID_WEBHOOK_SECRET = 'test-razorpay-webhook-secret-for-testing-only'


def make_valid_signature(payload: bytes, secret: str = VALID_WEBHOOK_SECRET) -> str:
    """Compute a valid Razorpay HMAC-SHA256 signature for testing."""
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


class TestWebhookSignatureVerification(TestCase):
    """Unit tests for the verify_razorpay_webhook_signature function."""

    def setUp(self):
        self.payload = b'{"event":"payment.captured","order_id":"order_abc123","payment_id":"pay_xyz789"}'
        self.valid_signature = make_valid_signature(self.payload)

    # ------------------------------------------------------------------ #
    #  Valid Signature                                                     #
    # ------------------------------------------------------------------ #

    @patch('apps.payments.webhook_verification.settings')
    def test_valid_signature_accepted(self, mock_settings):
        """A correctly-computed HMAC signature passes verification."""
        mock_settings.RAZORPAY_WEBHOOK_SECRET = VALID_WEBHOOK_SECRET
        mock_settings.DEBUG = False

        result = verify_razorpay_webhook_signature(self.payload, self.valid_signature)
        self.assertTrue(result)

    # ------------------------------------------------------------------ #
    #  Invalid / Tampered Signatures                                       #
    # ------------------------------------------------------------------ #

    @patch('apps.payments.webhook_verification.settings')
    def test_tampered_payload_rejected(self, mock_settings):
        """A valid signature on a different payload (tampered body) is rejected."""
        mock_settings.RAZORPAY_WEBHOOK_SECRET = VALID_WEBHOOK_SECRET
        mock_settings.DEBUG = False

        tampered_payload = b'{"event":"payment.captured","order_id":"FAKE","payment_id":"FAKE"}'
        with self.assertRaises(WebhookSignatureError) as ctx:
            verify_razorpay_webhook_signature(tampered_payload, self.valid_signature)

        self.assertIn('mismatch', str(ctx.exception).lower())

    @patch('apps.payments.webhook_verification.settings')
    def test_wrong_secret_rejected(self, mock_settings):
        """A signature computed with the wrong secret is rejected."""
        mock_settings.RAZORPAY_WEBHOOK_SECRET = VALID_WEBHOOK_SECRET
        mock_settings.DEBUG = False

        wrong_signature = make_valid_signature(self.payload, secret='wrong-secret')
        with self.assertRaises(WebhookSignatureError):
            verify_razorpay_webhook_signature(self.payload, wrong_signature)

    @patch('apps.payments.webhook_verification.settings')
    def test_empty_signature_rejected(self, mock_settings):
        """An empty X-Razorpay-Signature header is rejected."""
        mock_settings.RAZORPAY_WEBHOOK_SECRET = VALID_WEBHOOK_SECRET
        mock_settings.DEBUG = False

        with self.assertRaises(WebhookSignatureError) as ctx:
            verify_razorpay_webhook_signature(self.payload, '')

        self.assertIn('Missing', str(ctx.exception))

    @patch('apps.payments.webhook_verification.settings')
    def test_missing_signature_rejected(self, mock_settings):
        """None signature header is handled and rejected."""
        mock_settings.RAZORPAY_WEBHOOK_SECRET = VALID_WEBHOOK_SECRET
        mock_settings.DEBUG = False

        with self.assertRaises(WebhookSignatureError):
            verify_razorpay_webhook_signature(self.payload, None)

    # ------------------------------------------------------------------ #
    #  Production Safety: Missing Secret                                   #
    # ------------------------------------------------------------------ #

    @patch('apps.payments.webhook_verification.settings')
    def test_missing_secret_in_production_raises(self, mock_settings):
        """Missing RAZORPAY_WEBHOOK_SECRET in production mode raises an error."""
        mock_settings.RAZORPAY_WEBHOOK_SECRET = ''
        mock_settings.DEBUG = False

        with self.assertRaises(WebhookSignatureError) as ctx:
            verify_razorpay_webhook_signature(self.payload, self.valid_signature)

        self.assertIn('not configured', str(ctx.exception))

    @patch('apps.payments.webhook_verification.settings')
    def test_missing_secret_in_debug_skips_verification(self, mock_settings):
        """In DEBUG mode without a secret, verification is skipped (dev convenience)."""
        mock_settings.RAZORPAY_WEBHOOK_SECRET = ''
        mock_settings.DEBUG = True

        # Should not raise — returns True to allow local dev
        result = verify_razorpay_webhook_signature(self.payload, '')
        self.assertTrue(result)

    # ------------------------------------------------------------------ #
    #  Constant-Time Comparison (Anti-Timing Attack)                       #
    # ------------------------------------------------------------------ #

    @patch('apps.payments.webhook_verification.settings')
    def test_uses_constant_time_comparison(self, mock_settings):
        """Verifies hmac.compare_digest is used (not naive == comparison)."""
        mock_settings.RAZORPAY_WEBHOOK_SECRET = VALID_WEBHOOK_SECRET
        mock_settings.DEBUG = False

        import apps.payments.webhook_verification as wv
        import inspect
        source = inspect.getsource(wv.verify_razorpay_webhook_signature)
        self.assertIn('compare_digest', source,
                      "verify_razorpay_webhook_signature must use hmac.compare_digest for timing safety")


class TestPaymentWebhookViewSecurity(TestCase):
    """Integration tests: the webhook endpoint must reject unsigned requests."""

    def _make_webhook_payload(self):
        return {
            'event': 'payment.captured',
            'order_id': 'order_test123',
            'payment_id': 'pay_test456',
        }

    @patch('apps.payments.webhook_verification.settings')
    def test_webhook_rejects_missing_signature(self, mock_settings):
        """POST to /webhooks/payment/ without X-Razorpay-Signature returns 400."""
        mock_settings.RAZORPAY_WEBHOOK_SECRET = VALID_WEBHOOK_SECRET
        mock_settings.DEBUG = False

        payload_bytes = json.dumps(self._make_webhook_payload()).encode()
        response = self.client.post(
            '/api/v1/payments/webhook/',
            data=payload_bytes,
            content_type='application/json',
            # No X-Razorpay-Signature header
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])

    @patch('apps.payments.webhook_verification.settings')
    def test_webhook_rejects_tampered_signature(self, mock_settings):
        """POST with a forged signature returns 400."""
        mock_settings.RAZORPAY_WEBHOOK_SECRET = VALID_WEBHOOK_SECRET
        mock_settings.DEBUG = False

        payload_bytes = json.dumps(self._make_webhook_payload()).encode()
        response = self.client.post(
            '/api/v1/payments/webhook/',
            data=payload_bytes,
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE='forged-signature-that-wont-match',
        )
        self.assertEqual(response.status_code, 400)

    @patch('apps.payments.webhook_verification.settings')
    @patch('apps.payments.services.PaymentService.handle_payment_success')
    def test_webhook_accepts_valid_signature(self, mock_handle, mock_settings):
        """POST with valid HMAC signature is accepted and processed."""
        mock_settings.RAZORPAY_WEBHOOK_SECRET = VALID_WEBHOOK_SECRET
        mock_settings.DEBUG = False

        # Mock the payment
        from unittest.mock import MagicMock
        mock_payment = MagicMock()
        mock_payment.status = 'SUCCESS'
        mock_handle.return_value = mock_payment

        payload_dict = self._make_webhook_payload()
        payload_bytes = json.dumps(payload_dict).encode()
        valid_sig = make_valid_signature(payload_bytes, VALID_WEBHOOK_SECRET)

        response = self.client.post(
            '/api/v1/payments/webhook/',
            data=payload_bytes,
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE=valid_sig,
        )
        # 200 = signature verified and event processed
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
