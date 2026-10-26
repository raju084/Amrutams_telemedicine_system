from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from apps.common.views import HealthCheckView, ReadinessCheckView, DeepHealthCheckView

urlpatterns = [
    # Silences Chrome DevTools auto-probe (not a real route)
    path('.well-known/appspecific/com.chrome.devtools.json',
         lambda r: HttpResponse('{}', content_type='application/json'),
         name='chrome-devtools-probe'),

    # Admin Panel
    path('admin/', admin.site.urls),

    # Observability & Metrics
    path('', include('django_prometheus.urls')),
    path('api/v1/health/', HealthCheckView.as_view(), name='health-live'),
    path('api/v1/health/live/', HealthCheckView.as_view(), name='health-live-explicit'),
    path('api/v1/health/ready/', ReadinessCheckView.as_view(), name='health-ready'),
    path('api/v1/health/deep/', DeepHealthCheckView.as_view(), name='health-deep'),

    # OpenAPI 3.0 Documentation (sidecar = assets served locally, no CDN needed)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Domain API routes
    path('api/v1/auth/', include('apps.users.urls')),
    path('api/v1/doctors/', include('apps.doctors.urls')),
    path('api/v1/consultations/', include('apps.consultations.urls')),
    path('api/v1/prescriptions/', include('apps.prescriptions.urls')),
    path('api/v1/payments/', include('apps.payments.urls')),
    path('api/v1/audit/', include('apps.audit.urls')),
    path('api/v1/analytics/', include('apps.analytics.urls')),
]

# Serve static files in development (required for sidecar JS/CSS assets)
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

