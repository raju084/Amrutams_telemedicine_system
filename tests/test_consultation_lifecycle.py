import pytest
from datetime import date, time, timedelta
from decimal import Decimal
from rest_framework.test import APIClient
from apps.users.models import User
from apps.doctors.models import Doctor, AvailabilitySlot
from apps.consultations.models import Consultation
from apps.consultations.services import BookingService
from apps.payments.services import PaymentService

@pytest.mark.django_db
class TestConsultationLifecycleSaga:
    def setup_method(self):
        self.client = APIClient()
        self.patient = User.objects.create_user(
            email='saga_patient@example.com',
            password='Password123!',
            first_name='Kavita',
            last_name='Nair',
            role='PATIENT'
        )
        self.doc_user = User.objects.create_user(
            email='saga_doctor@amrutam.com',
            password='DocPassword123!',
            first_name='Dev',
            last_name='Pandey',
            role='DOCTOR'
        )
        self.doctor = Doctor.objects.create(
            user=self.doc_user,
            license_number='AYUSH-SAGA-777',
            specialization='KAYACHIKITSA',
            consultation_fee=Decimal('600.00'),
            is_verified=True
        )
        self.slot = AvailabilitySlot.objects.create(
            doctor=self.doctor,
            date=date.today() + timedelta(days=1),
            start_time=time(15, 0),
            end_time=time(15, 30),
            status=AvailabilitySlot.STATUS_AVAILABLE
        )

    def test_full_consultation_saga(self):
        # 1. Step 1: Patient reserves slot
        consultation = BookingService.reserve_slot(
            patient=self.patient,
            slot_id=self.slot.id,
            chief_complaint="Insomnia & Pitta aggravation"
        )
        assert consultation.status == Consultation.STATUS_REQUESTED
        self.slot.refresh_from_db()
        assert self.slot.status == AvailabilitySlot.STATUS_LOCKED

        # 2. Step 2: Payment Initiation & Webhook Confirmation
        payment = PaymentService.initiate_payment(consultation.id, "pay_saga_100")
        PaymentService.handle_payment_success(payment.gateway_order_id, "gateway_tx_100")

        consultation.refresh_from_db()
        assert consultation.status == Consultation.STATUS_CONFIRMED
        assert consultation.video_room_id is not None
        self.slot.refresh_from_db()
        assert self.slot.status == AvailabilitySlot.STATUS_BOOKED

        # 3. Step 3: Doctor starts consultation
        self.client.force_authenticate(user=self.doc_user)
        res_start = self.client.post(f'/api/v1/consultations/{consultation.id}/transition/', {
            'action': 'START'
        }, format='json')
        assert res_start.status_code == 200
        assert res_start.data['consultation']['status'] == Consultation.STATUS_IN_PROGRESS

        # 4. Step 4: Video Token generation
        res_video = self.client.get(f'/api/v1/consultations/{consultation.id}/video-token/')
        assert res_video.status_code == 200
        assert 'token' in res_video.data
        assert res_video.data['room_id'] == consultation.video_room_id

        # 5. Step 5: Doctor completes session
        res_complete = self.client.post(f'/api/v1/consultations/{consultation.id}/transition/', {
            'action': 'COMPLETE'
        }, format='json')
        assert res_complete.status_code == 200
        assert res_complete.data['consultation']['status'] == Consultation.STATUS_COMPLETED

    def test_cancellation_frees_slot_and_triggers_saga_compensation(self):
        consultation = BookingService.reserve_slot(
            patient=self.patient,
            slot_id=self.slot.id,
            chief_complaint="Mild indigestion"
        )
        self.client.force_authenticate(user=self.patient)

        res_cancel = self.client.post(f'/api/v1/consultations/{consultation.id}/transition/', {
            'action': 'CANCEL',
            'reason': 'Change of schedule'
        }, format='json')
        assert res_cancel.status_code == 200
        assert res_cancel.data['consultation']['status'] == Consultation.STATUS_CANCELLED

        # Slot must be liberated back to AVAILABLE
        self.slot.refresh_from_db()
        assert self.slot.status == AvailabilitySlot.STATUS_AVAILABLE
