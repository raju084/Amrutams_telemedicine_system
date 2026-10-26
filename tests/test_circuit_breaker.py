"""
Tests for the Redis-backed Circuit Breaker.

Validates the full 3-state machine:
  CLOSED → (threshold failures) → OPEN → (recovery_timeout) → HALF_OPEN → CLOSED
  HALF_OPEN → (failure) → OPEN

Run with: pytest tests/test_circuit_breaker.py -v
"""

import time
import pytest
from unittest.mock import patch, MagicMock
from django.test import TestCase
from apps.common.circuit_breaker import CircuitBreaker, CircuitBreakerOpen


class TestCircuitBreakerStateMachine(TestCase):
    """Unit tests for the 3-state circuit breaker machine."""

    def setUp(self):
        """Create a fresh test breaker with a low threshold for fast testing."""
        self.breaker = CircuitBreaker(
            name=f'test_breaker_{id(self)}',
            failure_threshold=3,
            recovery_timeout=30,
        )
        # Reset state in cache before each test
        from django.core.cache import cache
        cache.delete(f"circuit_breaker:{self.breaker.name}:state")
        cache.delete(f"circuit_breaker:{self.breaker.name}:failures")
        cache.delete(f"circuit_breaker:{self.breaker.name}:opened_at")

    # ------------------------------------------------------------------ #
    #  CLOSED State                                                        #
    # ------------------------------------------------------------------ #

    def test_initial_state_is_closed(self):
        """Breaker starts in CLOSED state."""
        self.assertEqual(self.breaker.state, CircuitBreaker.STATE_CLOSED)

    def test_successful_call_in_closed_state(self):
        """Successful calls in CLOSED state complete normally."""
        with self.breaker:
            result = 42  # Simulate successful external call

        self.assertEqual(self.breaker.state, CircuitBreaker.STATE_CLOSED)
        self.assertEqual(self.breaker.failure_count, 0)

    def test_failed_calls_increment_counter(self):
        """Failed calls increment the failure counter."""
        for i in range(2):
            try:
                with self.breaker:
                    raise ConnectionError("Service unavailable")
            except ConnectionError:
                pass

        self.assertEqual(self.breaker.failure_count, 2)
        self.assertEqual(self.breaker.state, CircuitBreaker.STATE_CLOSED)

    # ------------------------------------------------------------------ #
    #  CLOSED → OPEN Transition                                            #
    # ------------------------------------------------------------------ #

    def test_circuit_opens_after_threshold_failures(self):
        """After failure_threshold consecutive failures, circuit OPENS."""
        for _ in range(self.breaker.failure_threshold):
            try:
                with self.breaker:
                    raise ConnectionError("Service down")
            except ConnectionError:
                pass

        self.assertEqual(self.breaker.state, CircuitBreaker.STATE_OPEN)

    def test_open_circuit_rejects_requests(self):
        """OPEN circuit immediately raises CircuitBreakerOpen without calling the service."""
        # Trip the circuit
        for _ in range(self.breaker.failure_threshold):
            try:
                with self.breaker:
                    raise ConnectionError()
            except ConnectionError:
                pass

        # Next call should be rejected without hitting the service
        call_count = 0
        with self.assertRaises(CircuitBreakerOpen):
            with self.breaker:
                call_count += 1  # Should never reach here

        self.assertEqual(call_count, 0, "Service should not be called when circuit is OPEN")

    # ------------------------------------------------------------------ #
    #  OPEN → HALF_OPEN Transition                                         #
    # ------------------------------------------------------------------ #

    def test_circuit_transitions_to_half_open_after_recovery_timeout(self):
        """After recovery_timeout seconds, OPEN circuit allows a probe request."""
        # Trip the circuit
        for _ in range(self.breaker.failure_threshold):
            try:
                with self.breaker:
                    raise ConnectionError()
            except ConnectionError:
                pass

        self.assertEqual(self.breaker.state, CircuitBreaker.STATE_OPEN)

        # Mock the opened_at to be in the past (beyond recovery_timeout)
        past_time = str(time.time() - (self.breaker.recovery_timeout + 5))
        from django.core.cache import cache
        cache.set(f"circuit_breaker:{self.breaker.name}:opened_at", past_time)

        # Now the next call should be allowed (HALF_OPEN probe)
        self.assertTrue(self.breaker._should_allow_request())

    # ------------------------------------------------------------------ #
    #  HALF_OPEN Transitions                                               #
    # ------------------------------------------------------------------ #

    def test_successful_probe_closes_circuit(self):
        """A successful probe in HALF_OPEN state closes the circuit."""
        # Force HALF_OPEN state
        self.breaker._set_state(CircuitBreaker.STATE_HALF_OPEN)

        with self.breaker:
            pass  # Simulate successful probe

        self.assertEqual(self.breaker.state, CircuitBreaker.STATE_CLOSED)
        self.assertEqual(self.breaker.failure_count, 0)

    def test_failed_probe_reopens_circuit(self):
        """A failed probe in HALF_OPEN state reopens the circuit."""
        self.breaker._set_state(CircuitBreaker.STATE_HALF_OPEN)

        try:
            with self.breaker:
                raise ConnectionError("Service still down")
        except ConnectionError:
            pass

        self.assertEqual(self.breaker.state, CircuitBreaker.STATE_OPEN)

    # ------------------------------------------------------------------ #
    #  Success Resets Failure Counter                                      #
    # ------------------------------------------------------------------ #

    def test_success_after_failures_resets_counter(self):
        """A success in CLOSED state resets the failure counter."""
        for _ in range(2):
            try:
                with self.breaker:
                    raise ConnectionError()
            except ConnectionError:
                pass

        self.assertEqual(self.breaker.failure_count, 2)

        with self.breaker:
            pass  # Success

        self.assertEqual(self.breaker.failure_count, 0)

    # ------------------------------------------------------------------ #
    #  Decorator Interface                                                 #
    # ------------------------------------------------------------------ #

    def test_decorator_interface(self):
        """Circuit breaker works as a function decorator."""
        @self.breaker
        def call_external_service():
            return "success"

        result = call_external_service()
        self.assertEqual(result, "success")

    def test_decorator_raises_circuit_open_when_tripped(self):
        """Decorated function raises CircuitBreakerOpen when circuit is OPEN."""
        self.breaker._set_state(CircuitBreaker.STATE_OPEN)
        from django.core.cache import cache
        cache.set(
            f"circuit_breaker:{self.breaker.name}:opened_at",
            str(time.time()),  # Just opened
        )

        @self.breaker
        def call_external_service():
            return "success"

        with self.assertRaises(CircuitBreakerOpen):
            call_external_service()

    # ------------------------------------------------------------------ #
    #  Status/Health                                                       #
    # ------------------------------------------------------------------ #

    def test_get_status_returns_full_info(self):
        """get_status() returns complete breaker state for health endpoints."""
        status = self.breaker.get_status()

        self.assertIn('name', status)
        self.assertIn('state', status)
        self.assertIn('failure_count', status)
        self.assertIn('failure_threshold', status)
        self.assertIn('recovery_timeout_seconds', status)
        self.assertEqual(status['name'], self.breaker.name)
