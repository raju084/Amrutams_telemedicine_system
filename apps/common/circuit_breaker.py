"""
Circuit Breaker Pattern for External Service Resilience.

Implements the classic 3-state circuit breaker (CLOSED → OPEN → HALF-OPEN)
using Redis as the shared state store so multiple Gunicorn workers share
the same breaker state.

States:
    CLOSED   — Normal operation; calls pass through. Failure counter tracks errors.
    OPEN     — Circuit tripped; calls are rejected immediately without hitting the
               downstream service. Protects against cascading failures.
    HALF_OPEN — After cooldown, one probe request is allowed through. If it
                succeeds, circuit closes. If it fails, it reopens.

Usage:
    breaker = CircuitBreaker('razorpay_gateway', failure_threshold=5, recovery_timeout=60)

    with breaker:
        response = razorpay_client.orders.create(...)

Or as a decorator:
    @CircuitBreaker('sms_provider', failure_threshold=3)
    def send_sms(phone, message):
        ...
"""

import time
import logging
import functools
from django.core.cache import cache

logger = logging.getLogger(__name__)


class CircuitBreakerOpen(Exception):
    """Raised when a circuit breaker is OPEN and calls are being rejected."""
    pass


class CircuitBreaker:
    """
    Thread-safe, Redis-backed circuit breaker for external service calls.

    Args:
        name: Unique identifier for this breaker (used as Redis key prefix).
        failure_threshold: Number of consecutive failures before the circuit opens.
        recovery_timeout: Seconds to wait in OPEN state before allowing a probe.
        expected_exception: Exception type(s) that count as failures (default: Exception).
    """

    STATE_CLOSED = 'closed'
    STATE_OPEN = 'open'
    STATE_HALF_OPEN = 'half_open'

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception=Exception,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self._state_key = f"circuit_breaker:{name}:state"
        self._failure_key = f"circuit_breaker:{name}:failures"
        self._opened_at_key = f"circuit_breaker:{name}:opened_at"

    # ------------------------------------------------------------------ #
    #  State Management (Redis-backed)                                     #
    # ------------------------------------------------------------------ #

    @property
    def state(self) -> str:
        return cache.get(self._state_key, self.STATE_CLOSED)

    @property
    def failure_count(self) -> int:
        return int(cache.get(self._failure_key, 0))

    @property
    def opened_at(self):
        return cache.get(self._opened_at_key)

    def _set_state(self, state: str, ttl: int = None):
        cache.set(self._state_key, state, timeout=ttl or self.recovery_timeout * 10)
        logger.info("CircuitBreaker[%s] state → %s", self.name, state)

    def _increment_failure(self):
        try:
            cache.incr(self._failure_key)
        except ValueError:
            cache.set(self._failure_key, 1, timeout=self.recovery_timeout * 10)

    def _reset_failure_count(self):
        cache.set(self._failure_key, 0, timeout=self.recovery_timeout * 10)

    # ------------------------------------------------------------------ #
    #  Core State Machine                                                  #
    # ------------------------------------------------------------------ #

    def _should_allow_request(self) -> bool:
        """Determine if the current request should be passed through."""
        state = self.state

        if state == self.STATE_CLOSED:
            return True

        if state == self.STATE_OPEN:
            opened_at = self.opened_at
            if opened_at and (time.time() - float(opened_at)) >= self.recovery_timeout:
                # Recovery window elapsed — move to HALF_OPEN for probe
                self._set_state(self.STATE_HALF_OPEN)
                logger.info("CircuitBreaker[%s] entering HALF_OPEN — sending probe request.", self.name)
                return True
            return False  # Still OPEN — reject request

        if state == self.STATE_HALF_OPEN:
            return True  # Allow the single probe request

        return True

    def _on_success(self):
        """Called when a request succeeds."""
        state = self.state
        if state in (self.STATE_HALF_OPEN, self.STATE_OPEN):
            logger.info("CircuitBreaker[%s] probe succeeded — closing circuit.", self.name)
        self._set_state(self.STATE_CLOSED)
        self._reset_failure_count()

    def _on_failure(self, exc: Exception):
        """Called when a request fails."""
        self._increment_failure()
        failures = self.failure_count
        state = self.state

        if state == self.STATE_HALF_OPEN:
            # Probe failed — re-open immediately
            logger.warning(
                "CircuitBreaker[%s] probe FAILED — reopening circuit. error=%s",
                self.name, exc
            )
            self._open_circuit()
        elif failures >= self.failure_threshold:
            logger.warning(
                "CircuitBreaker[%s] failure threshold reached (%d/%d) — OPENING circuit. error=%s",
                self.name, failures, self.failure_threshold, exc
            )
            self._open_circuit()
        else:
            logger.debug(
                "CircuitBreaker[%s] failure %d/%d. error=%s",
                self.name, failures, self.failure_threshold, exc
            )

    def _open_circuit(self):
        cache.set(self._opened_at_key, str(time.time()), timeout=self.recovery_timeout * 10)
        self._set_state(self.STATE_OPEN)

    # ------------------------------------------------------------------ #
    #  Context Manager Interface                                           #
    # ------------------------------------------------------------------ #

    def __enter__(self):
        if not self._should_allow_request():
            raise CircuitBreakerOpen(
                f"Circuit breaker '{self.name}' is OPEN. "
                f"Service unavailable, retry after {self.recovery_timeout}s."
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self._on_success()
        elif exc_type and issubclass(exc_type, self.expected_exception):
            self._on_failure(exc_val)
            return False  # Re-raise the original exception
        return False

    # ------------------------------------------------------------------ #
    #  Decorator Interface                                                 #
    # ------------------------------------------------------------------ #

    def __call__(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with self:
                return func(*args, **kwargs)
        return wrapper

    # ------------------------------------------------------------------ #
    #  Status / Metrics                                                    #
    # ------------------------------------------------------------------ #

    def get_status(self) -> dict:
        """Returns current breaker status for health-check endpoints."""
        return {
            'name': self.name,
            'state': self.state,
            'failure_count': self.failure_count,
            'failure_threshold': self.failure_threshold,
            'recovery_timeout_seconds': self.recovery_timeout,
            'opened_at': self.opened_at,
        }


# --------------------------------------------------------------------------- #
#  Pre-configured Breakers for External Services                               #
# --------------------------------------------------------------------------- #

#: Circuit breaker for Razorpay payment gateway
razorpay_breaker = CircuitBreaker(
    name='razorpay_gateway',
    failure_threshold=5,
    recovery_timeout=60,
)

#: Circuit breaker for notification provider (email/SMS)
notification_breaker = CircuitBreaker(
    name='notification_provider',
    failure_threshold=3,
    recovery_timeout=30,
)

#: Circuit breaker for video platform (Agora/Twilio)
video_platform_breaker = CircuitBreaker(
    name='video_platform',
    failure_threshold=5,
    recovery_timeout=120,
)
