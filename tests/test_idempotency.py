import pytest
import uuid
from datetime import date, time, timedelta
from decimal import Decimal
from rest_framework.test import APIClient
from apps.users.models import User
from apps.doctors.models import Doctor, AvailabilitySlot
from apps.consultations.models import Consultation
from apps.payments.services import PaymentService
from apps.payments.models import Payment

@pytest.mark.django_db
class TestIdempotencyMechanism:
    def setup_method(self):
        self.client = APIClient()
        self.patient = User.objects.create_user(
            email='idempotent_patient@example.com',
            password='Password123!',
            role='PATIENT'
        )
        self.client.force_authenticate(user=self.patient)

        self.doc_user = User.objects.create_user(
            email='dr.idemp@amrutam.com',
            password='DocPassword123!',
            role='DOCTOR'
        )
        self.doctor = Doctor.objects.create(
            user=self.doc_user,
            license_number='AYUSH-IDEMP-001',
            specialization='KAYACHIKITSA',
            consultation_fee=Decimal('500.00'),
            is_verified=True
        )
        self.slot = AvailabilitySlot.objects.create(
            doctor=self.doctor,
            date=date.today() + timedelta(days=2),
            start_time=time(14, 0),
            end_time=time(14, 30),
            status=AvailabilitySlot.STATUS_AVAILABLE
        )

    def test_consultation_booking_idempotency_key(self):
        idempotency_key = f"key_{uuid.uuid4()}"
        payload = {
            'slot_id': str(self.slot.id),
            'chief_complaint': 'Chronic fatigue',
            'symptoms': 'Brain fog, low energy'
        }

        # First request: Creates reservation
        res1 = self.client.post(
            '/api/v1/consultations/book/',
            payload,
            format='json',
            HTTP_IDEMPOTENCY_KEY=idempotency_key
        )
        assert res1.status_code == 201
        first_consultation_id = res1.data['consultation']['id']
        assert Consultation.objects.count() == 1

        # Second request with SAME Idempotency-Key: Must return cached response without duplicate creation
        res2 = self.client.post(
            '/api/v1/consultations/book/',
            payload,
            format='json',
            HTTP_IDEMPOTENCY_KEY=idempotency_key
        )
        assert res2.status_code == 201
        assert res2.has_header('X-Cache-Lookup')
        assert 'HIT' in res2['X-Cache-Lookup']
        assert res2.json()['consultation']['id'] == first_consultation_id
        # Crucial check: still exactly 1 consultation in DB, no duplicate side-effect!
        assert Consultation.objects.count() == 1

    def test_payment_service_idempotency(self):
        # Create a consultation
        consultation = Consultation.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            slot=self.slot,
            status=Consultation.STATUS_REQUESTED,
            chief_complaint="Fatigue"
        )
        pay_key = f"pay_key_{uuid.uuid4()}"

        # First call initiates payment
        p1 = PaymentService.initiate_payment(consultation.id, pay_key)
        assert Payment.objects.count() == 1
        assert p1.idempotency_key == pay_key

        # Second call with same idempotency key returns identical payment object
        p2 = PaymentService.initiate_payment(consultation.id, pay_key)
        assert p1.id == p2.id
        assert Payment.objects.count() == 1
