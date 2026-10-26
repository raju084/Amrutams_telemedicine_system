import pytest
import pyotp
from rest_framework.test import APIClient
from apps.users.models import User, PatientProfile

@pytest.mark.django_db
class TestAuthenticationAndMFA:
    def setup_method(self):
        self.client = APIClient()

    def test_patient_registration_with_phi_encryption(self):
        payload = {
            'email': 'newpatient@example.com',
            'password': 'StrongPassword123!',
            'first_name': 'Aarav',
            'last_name': 'Mehta',
            'phone_number': '+919876543299',
            'role': 'PATIENT',
            'profile': {
                'date_of_birth': '1992-04-12',
                'gender': 'MALE',
                'blood_group': 'B+',
                'emergency_contact': '+919876543200',
                'allergies': 'Penicillin, Dust mite',
                'chronic_conditions': 'Vata aggravation causing joint stiffness',
                'prakriti': 'VATA_PITTA'
            }
        }
        res = self.client.post('/api/v1/auth/register/', payload, format='json')
        assert res.status_code == 201
        assert res.data['success'] is True
        assert 'tokens' in res.data
        assert res.data['user']['email'] == 'newpatient@example.com'

        # Verify Database PHI is stored encrypted
        user = User.objects.get(email='newpatient@example.com')
        profile = user.patient_profile
        # Raw encrypted field should not contain plain text
        assert 'Penicillin' not in profile._allergies_encrypted
        # Property decryptor decrypts seamlessly
        assert profile.allergies == 'Penicillin, Dust mite'

    def test_login_flow(self):
        user = User.objects.create_user(
            email='testuser@example.com',
            password='TestPassword123!',
            first_name='Test',
            last_name='User',
            role='PATIENT'
        )
        res = self.client.post('/api/v1/auth/login/', {
            'email': 'testuser@example.com',
            'password': 'TestPassword123!'
        }, format='json')
        assert res.status_code == 200
        assert res.data['success'] is True
        assert res.data['mfa_required'] is False
        assert 'access' in res.data['tokens']
        assert 'refresh' in res.data['tokens']

    def test_mfa_setup_and_challenge_flow(self):
        # 1. Create User
        user = User.objects.create_user(
            email='mfapatient@example.com',
            password='TestPassword123!',
            role='PATIENT'
        )
        self.client.force_authenticate(user=user)

        # 2. Setup MFA
        setup_res = self.client.post('/api/v1/auth/mfa/setup/')
        assert setup_res.status_code == 200
        secret = setup_res.data['secret']
        assert secret is not None
        assert 'otpauth://' in setup_res.data['provisioning_uri']

        # 3. Verify MFA activation with valid TOTP code
        totp = pyotp.TOTP(secret)
        otp = totp.now()

        verify_res = self.client.post('/api/v1/auth/mfa/verify/', {'otp': otp}, format='json')
        assert verify_res.status_code == 200
        assert verify_res.data['success'] is True

        user.refresh_from_db()
        assert user.mfa_enabled is True

        # 4. Login now challenges with MFA
        self.client.force_authenticate(user=None)
        login_res = self.client.post('/api/v1/auth/login/', {
            'email': 'mfapatient@example.com',
            'password': 'TestPassword123!'
        }, format='json')
        assert login_res.status_code == 200
        assert login_res.data['mfa_required'] is True
        temp_token = login_res.data['temp_token']

        # 5. Complete MFA login challenge
        otp = totp.now()
        challenge_res = self.client.post('/api/v1/auth/mfa/verify/', {
            'otp': otp,
            'temp_token': temp_token
        }, format='json')
        assert challenge_res.status_code == 200
        assert 'access' in challenge_res.data['tokens']
