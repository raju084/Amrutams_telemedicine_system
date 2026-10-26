import pytest
from rest_framework.test import APIClient
from apps.users.models import User

@pytest.mark.django_db
class TestAdminAnalytics:
    def setup_method(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email='admin_analyst@amrutam.com',
            password='AdminPassword123!',
            role='ADMIN',
            is_staff=True
        )
        self.patient = User.objects.create_user(
            email='normal_patient@example.com',
            password='Password123!',
            role='PATIENT'
        )

    def test_admin_can_access_analytics(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.get('/api/v1/analytics/overview/')
        assert res.status_code == 200
        assert res.data['success'] is True
        assert 'consultations' in res.data
        assert 'revenue' in res.data
        assert 'doctor_utilization' in res.data
        assert res.data['sla_observability']['target_daily_capacity'] == 100000

    def test_non_admin_forbidden(self):
        self.client.force_authenticate(user=self.patient)
        res = self.client.get('/api/v1/analytics/overview/')
        assert res.status_code == 403
