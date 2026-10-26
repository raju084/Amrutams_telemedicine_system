from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework import status, serializers
from drf_spectacular.utils import extend_schema, inline_serializer
from django.db import connection
from django.core.cache import cache
import os
import time

START_TIME = time.time()

class HealthCheckView(APIView):
    """
    Kubernetes Liveness Probe: Returns HTTP 200 if process is running.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Health & Observability'],
        responses={
            200: inline_serializer(
                name='LivenessResponse',
                fields={
                    'status': serializers.CharField(),
                    'uptime_seconds': serializers.IntegerField(),
                    'environment': serializers.CharField(),
                    'version': serializers.CharField(),
                }
            )
        }
    )
    def get(self, request):
        return Response({
            'status': 'HEALTHY',
            'uptime_seconds': int(time.time() - START_TIME),
            'environment': 'development' if os.environ.get('DEBUG', 'False').lower() == 'true' else 'production',
            'version': '1.0.0'
        }, status=status.HTTP_200_OK)


class ReadinessCheckView(APIView):
    """
    Kubernetes Readiness Probe: Verifies live connectivity to PostgreSQL and Redis.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Health & Observability'],
        responses={
            200: inline_serializer(
                name='ReadinessResponse',
                fields={
                    'status': serializers.CharField(),
                    'dependencies': serializers.DictField(),
                    'timestamp': serializers.FloatField(),
                }
            )
        }
    )
    def get(self, request):
        checks = {}
        all_passed = True

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
                cursor.fetchone()
            checks['database'] = 'CONNECTED'
        except Exception as e:
            checks['database'] = f'ERROR: {str(e)}'
            all_passed = False

        try:
            cache.set('health_check_ping', 'pong', timeout=5)
            val = cache.get('health_check_ping')
            checks['cache_redis'] = 'CONNECTED' if val == 'pong' else 'CACHE_MISMATCH'
        except Exception as e:
            checks['cache_redis'] = f'ERROR: {str(e)}'
            all_passed = False

        http_status = status.HTTP_200_OK if all_passed else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response({
            'status': 'READY' if all_passed else 'DEGRADED',
            'dependencies': checks,
            'timestamp': time.time()
        }, status=http_status)


class DeepHealthCheckView(APIView):
    """
    Deep health check for SRE dashboards: includes circuit breaker states
    and service dependency status. Not used as a Kubernetes probe.
    Protected: requires authentication so it doesn't expose internals publicly.
    """
    permission_classes = [IsAdminUser]  # Exposes circuit breaker & service topology — admin only

    @extend_schema(
        tags=['Health & Observability'],
        responses={
            200: inline_serializer(
                name='DeepHealthResponse',
                fields={
                    'status': serializers.CharField(),
                    'uptime_seconds': serializers.IntegerField(),
                    'dependencies': serializers.DictField(),
                    'circuit_breakers': serializers.DictField(),
                    'timestamp': serializers.FloatField(),
                }
            )
        }
    )
    def get(self, request):
        from apps.common.circuit_breaker import (
            razorpay_breaker,
            notification_breaker,
            video_platform_breaker,
        )

        checks = {}

        # Database check
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
            checks['database'] = {'status': 'CONNECTED'}
        except Exception as e:
            checks['database'] = {'status': 'ERROR', 'detail': str(e)}

        # Redis / Cache check
        try:
            cache.set('deep_health_ping', 'pong', timeout=5)
            val = cache.get('deep_health_ping')
            checks['redis'] = {'status': 'CONNECTED' if val == 'pong' else 'MISMATCH'}
        except Exception as e:
            checks['redis'] = {'status': 'ERROR', 'detail': str(e)}

        all_ok = all(v.get('status') in ('CONNECTED',) for v in checks.values())

        return Response({
            'status': 'HEALTHY' if all_ok else 'DEGRADED',
            'uptime_seconds': int(time.time() - START_TIME),
            'dependencies': checks,
            'circuit_breakers': {
                'razorpay_gateway': razorpay_breaker.get_status(),
                'notification_provider': notification_breaker.get_status(),
                'video_platform': video_platform_breaker.get_status(),
            },
            'timestamp': time.time(),
        }, status=status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE)

