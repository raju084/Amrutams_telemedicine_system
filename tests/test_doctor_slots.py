import pytest
from datetime import date, time, timedelta
from decimal import Decimal
from rest_framework.test import APIClient
from apps.users.models import User
from apps.doctors.models import Doctor, AvailabilitySlot

@pytest.mark.django_db
class TestDoctorAvailabilityAndSearch:
    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='dr.kalyan@amrutam.com',
            password='DocPassword123!',
            first_name='Kalyan',
            last_name='Verma',
            role='DOCTOR'
        )
        self.doctor = Doctor.objects.create(
            user=self.user,
            license_number='AYUSH-DOC-TEST-101',
            specialization='PANCHAKARMA',
            qualification='MD Ayurveda',
            experience_years=10,
            consultation_fee=Decimal('1000.00'),
            rating=Decimal('4.9'),
            is_verified=True
        )

    def test_search_and_filter_doctors(self):
        res = self.client.get('/api/v1/doctors/?specialization=PANCHAKARMA&max_fee=1200')
        assert res.status_code == 200
        assert len(res.data['results']) >= 1
        assert res.data['results'][0]['specialization'] == 'PANCHAKARMA'

    def test_batch_slot_generation(self):
        self.client.force_authenticate(user=self.user)
        target_date = date.today() + timedelta(days=2)
        payload = {
            'date': str(target_date),
            'start_time': '09:00:00',
            'end_time': '11:00:00',
            'slot_duration_minutes': 30
        }
        res = self.client.post('/api/v1/doctors/slots/batch-create/', payload, format='json')
        assert res.status_code == 201
        assert res.data['created_slots_count'] == 4

        # Verify slots in database
        slots = AvailabilitySlot.objects.filter(doctor=self.doctor, date=target_date)
        assert slots.count() == 4

    def test_slot_uniqueness_constraint(self):
        target_date = date.today() + timedelta(days=3)
        AvailabilitySlot.objects.create(
            doctor=self.doctor,
            date=target_date,
            start_time=time(10, 0),
            end_time=time(10, 30),
            status=AvailabilitySlot.STATUS_AVAILABLE
        )
        # Attempt duplicate slot
        with pytest.raises(Exception):
            AvailabilitySlot.objects.create(
                doctor=self.doctor,
                date=target_date,
                start_time=time(10, 0),
                end_time=time(10, 30),
                status=AvailabilitySlot.STATUS_AVAILABLE
            )
