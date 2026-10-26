import pytest
import uuid
from django.core.exceptions import PermissionDenied
from rest_framework.test import APIClient
from apps.users.models import User
from apps.audit.models import AuditLog

@pytest.mark.django_db
class TestAuditTrailAndTamperEvidence:
    def setup_method(self):
        self.client = APIClient()
        self.auditor = User.objects.create_user(
            email='compliance_auditor@amrutam.com',
            password='AuditorPassword123!',
            role='AUDITOR'
        )

    def test_audit_log_immutability_enforcement(self):
        log = AuditLog.objects.create(
            user_id=uuid.uuid4(),
            user_email='actor@example.com',
            user_role='DOCTOR',
            action='PRESCRIPTION_ISSUED',
            resource_type='Prescription',
            resource_id=str(uuid.uuid4()),
            payload_diff={'status': 'SIGNED'}
        )
        assert log.log_hash != ''

        # Immutability Rule 1: Cannot update existing record
        with pytest.raises(PermissionDenied):
            log.action = 'TAMPERED_ACTION'
            log.save()

        # Immutability Rule 2: Cannot delete audit record
        with pytest.raises(PermissionDenied):
            log.delete()

    def test_audit_hash_chain_verification_endpoint(self):
        # Create a series of sequential audit records
        log1 = AuditLog.objects.create(
            user_email='u1@example.com',
            action='LOGIN_SUCCESS',
            resource_type='User',
            resource_id='1'
        )
        log2 = AuditLog.objects.create(
            user_email='u1@example.com',
            action='SLOT_BOOKED',
            resource_type='Consultation',
            resource_id='10'
        )
        # Check chaining
        assert log2.previous_log_hash == log1.log_hash

        # Test Auditor verification endpoint
        self.client.force_authenticate(user=self.auditor)
        res = self.client.get('/api/v1/audit/verify-chain/')
        assert res.status_code == 200
        assert res.data['chain_integrity'] == 'VALID'
        assert len(res.data['tampered_records']) == 0
