import pytest
from datetime import date, time, timedelta
from decimal import Decimal
from rest_framework.test import APIClient
from apps.users.models import User
from apps.doctors.models import Doctor, AvailabilitySlot
from apps.consultations.models import Consultation
from apps.prescriptions.models import Prescription, PrescriptionItem

@pytest.mark.django_db
class TestDigitalPrescriptionsAndSignatures:
    def setup_method(self):
        self.client = APIClient()
        self.patient = User.objects.create_user(
            email='rx_patient@example.com',
            password='Password123!',
            first_name='Sunita',
            last_name='Rao',
            role='PATIENT'
        )
        self.doc_user = User.objects.create_user(
            email='dr.rx@amrutam.com',
            password='DocPassword123!',
            first_name='Bhavna',
            last_name='Acharya',
            role='DOCTOR'
        )
        self.doctor = Doctor.objects.create(
            user=self.doc_user,
            license_number='AYUSH-RX-2026',
            specialization='KAYACHIKITSA',
            consultation_fee=Decimal('500.00'),
            is_verified=True
        )
        self.slot = AvailabilitySlot.objects.create(
            doctor=self.doctor,
            date=date.today(),
            start_time=time(10, 0),
            end_time=time(10, 30),
            status=AvailabilitySlot.STATUS_BOOKED
        )
        self.consultation = Consultation.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            slot=self.slot,
            status=Consultation.STATUS_IN_PROGRESS,
            chief_complaint="Severe indigestion and heartburn"
        )

    def test_prescription_creation_and_cryptographic_verification(self):
        self.client.force_authenticate(user=self.doc_user)
        payload = {
            'consultation': str(self.consultation.id),
            'diagnosis': 'Amlapitta (Hyperacidity due to aggravated Pitta dosha)',
            'dietary_advice': 'Avoid fermented, oily, and sour foods. Drink cooling coconut water.',
            'lifestyle_recommendations': 'Early dinner before 7:30 PM. 10 minutes Vajrasana after meals.',
            'follow_up_date': str(date.today() + timedelta(days=14)),
            'items': [
                {
                    'medicine_name': 'Amrutam Shankh Vati',
                    'form': 'VATI',
                    'dosage': '1 tablet',
                    'frequency': 'Twice daily',
                    'timing': 'AFTER_MEALS',
                    'anupana': 'Warm Water',
                    'duration_days': 15,
                    'instructions': 'Chew gently after meals'
                },
                {
                    'medicine_name': 'Avipattikar Churna',
                    'form': 'CHURNA',
                    'dosage': '3 grams',
                    'frequency': 'Once at bedtime',
                    'timing': 'BEDTIME',
                    'anupana': 'Lukewarm Water',
                    'duration_days': 15,
                    'instructions': 'Take 30 mins before sleep'
                }
            ]
        }
        res = self.client.post('/api/v1/prescriptions/', payload, format='json')
        assert res.status_code == 201
        assert res.data['success'] is True
        prescription_id = res.data['prescription']['id']
        digital_signature = res.data['prescription']['digital_signature']
        assert digital_signature is not None
        assert len(digital_signature) == 64  # SHA-256 hexdigest

        # Test Public Signature Verification endpoint
        self.client.force_authenticate(user=None)
        verify_res = self.client.get(f'/api/v1/prescriptions/{prescription_id}/verify-signature/')
        assert verify_res.status_code == 200
        assert verify_res.data['signature_valid'] is True
        assert verify_res.data['status'] == 'AUTHENTIC & VERIFIED'

    def test_tampered_prescription_signature_fails(self):
        self.client.force_authenticate(user=self.doc_user)
        payload = {
            'consultation': str(self.consultation.id),
            'diagnosis': 'Original diagnosis',
            'items': [
                {
                    'medicine_name': 'Herbal Tea',
                    'form': 'KASHAYA',
                    'dosage': '1 cup',
                    'frequency': 'Daily',
                    'timing': 'BEFORE_MEALS',
                    'anupana': 'Warm Water',
                    'duration_days': 7
                }
            ]
        }
        res = self.client.post('/api/v1/prescriptions/', payload, format='json')
        prescription_id = res.data['prescription']['id']

        # Simulate unauthorized direct database alteration / tampering
        prescription = Prescription.objects.get(id=prescription_id)
        prescription.diagnosis = "MALICIOUSLY ALTERED DIAGNOSIS"
        prescription.save(update_fields=['diagnosis'])

        # Verification endpoint should catch the tampering immediately
        verify_res = self.client.get(f'/api/v1/prescriptions/{prescription_id}/verify-signature/')
        assert verify_res.status_code == 200
        assert verify_res.data['signature_valid'] is False
        assert verify_res.data['status'] == 'TAMPERED OR INVALID SIGNATURE'
