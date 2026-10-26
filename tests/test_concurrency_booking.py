import pytest
import concurrent.futures
from datetime import date, time, timedelta
from decimal import Decimal
from django.db import connection
from apps.users.models import User
from apps.doctors.models import Doctor, AvailabilitySlot
from apps.consultations.services import BookingService
from rest_framework.exceptions import ValidationError

@pytest.mark.django_db(transaction=True)
class TestConcurrencyAndDoubleBookingPrevention:
    def setup_method(self):
        self.doc_user = User.objects.create_user(
            email='dr.race@amrutam.com',
            password='DocPassword123!',
            role='DOCTOR'
        )
        self.doctor = Doctor.objects.create(
            user=self.doc_user,
            license_number='AYUSH-RACE-999',
            specialization='KAYACHIKITSA',
            consultation_fee=Decimal('500.00'),
            is_verified=True
        )
        self.slot = AvailabilitySlot.objects.create(
            doctor=self.doctor,
            date=date.today() + timedelta(days=1),
            start_time=time(11, 0),
            end_time=time(11, 30),
            status=AvailabilitySlot.STATUS_AVAILABLE
        )
        # Create 10 distinct patients competing for this 1 single slot
        self.patients = [
            User.objects.create_user(
                email=f'competing_patient_{i}@example.com',
                password='Password123!',
                role='PATIENT'
            )
            for i in range(10)
        ]

    def test_high_concurrency_slot_race_condition(self):
        """
        Simulate 10 simultaneous patients attempting to reserve the exact same slot concurrently.
        Guarantees that EXACTLY ONE reservation succeeds and 9 fail with ValidationError.
        Zero double-booking!
        """
        results = []
        slot_id = self.slot.id

        def attempt_booking(patient):
            # Close stale connection in thread
            connection.close()
            try:
                consultation = BookingService.reserve_slot(
                    patient=patient,
                    slot_id=slot_id,
                    chief_complaint="Severe migraine"
                )
                return ('SUCCESS', consultation.id)
            except ValidationError as err:
                return ('FAILED_CONFLICT', str(err))
            except Exception as e:
                return ('FAILED_EXCEPTION', str(e))

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(attempt_booking, p) for p in self.patients]
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())

        success_count = sum(1 for status, _ in results if status == 'SUCCESS')
        conflict_count = sum(1 for status, _ in results if status == 'FAILED_CONFLICT')

        # Exactly ONE must succeed
        assert success_count == 1, f"Expected exactly 1 success, but got {success_count}. Double booking occurred!"
        assert conflict_count == 9, f"Expected 9 conflict failures, got {conflict_count}"

        # Slot state must be LOCKED and cannot be booked again
        self.slot.refresh_from_db()
        assert self.slot.status == AvailabilitySlot.STATUS_LOCKED
        assert self.slot.lock_token is not None
