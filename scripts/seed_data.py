import os
import sys
import django
from datetime import date, timedelta, time
from decimal import Decimal

# Setup Django Environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'amrutam_core.settings')
django.setup()

from apps.users.models import User, PatientProfile
from apps.doctors.models import Doctor, AvailabilitySlot
from apps.consultations.models import Consultation
from apps.consultations.services import BookingService
from apps.prescriptions.models import Prescription, PrescriptionItem
from apps.payments.models import Payment
from apps.payments.services import PaymentService
from apps.audit.models import AuditLog
from apps.common.crypto import generate_prescription_signature

def run():
    print("[*] Seeding Amrutam Telemedicine database...")

    # 1. Superuser / Admin
    admin_user, created = User.objects.get_or_create(
        email='admin@amrutam.com',
        defaults={
            'first_name': 'Amrutam',
            'last_name': 'Administrator',
            'role': User.ROLE_ADMIN,
            'is_staff': True,
            'is_superuser': True,
            'is_verified': True
        }
    )
    if created:
        admin_user.set_password('AmrutamAdmin2026!')
        admin_user.save()
        print("  [+] Created Admin: admin@amrutam.com (Password: AmrutamAdmin2026!)")

    # 2. Compliance Auditor
    auditor_user, created = User.objects.get_or_create(
        email='auditor@amrutam.com',
        defaults={
            'first_name': 'Compliance',
            'last_name': 'Officer',
            'role': User.ROLE_AUDITOR,
            'is_staff': False,
            'is_verified': True
        }
    )
    if created:
        auditor_user.set_password('AmrutamAuditor2026!')
        auditor_user.save()
        print("  [+] Created Auditor: auditor@amrutam.com (Password: AmrutamAuditor2026!)")

    # 3. Ayurvedic Doctors
    doctors_data = [
        {
            'email': 'dr.sharma@amrutam.com',
            'first_name': 'Ananya',
            'last_name': 'Sharma',
            'specialization': 'KAYACHIKITSA',
            'qualification': 'BAMS, MD (Ayurveda - Kayachikitsa), Banaras Hindu University',
            'license_number': 'AYUSH-DEL-2015-8941',
            'experience_years': 12,
            'fee': Decimal('800.00'),
            'rating': Decimal('4.95'),
            'bio': 'Specialist in metabolic health, chronic gut disorders, and holistic herbal formulations.'
        },
        {
            'email': 'dr.varma@amrutam.com',
            'first_name': 'Vikram',
            'last_name': 'Varma',
            'specialization': 'PANCHAKARMA',
            'qualification': 'BAMS, Fellowship in Panchakarma (Kerala Ayurveda Academy)',
            'license_number': 'AYUSH-KER-2018-4421',
            'experience_years': 8,
            'fee': Decimal('1200.00'),
            'rating': Decimal('4.90'),
            'bio': 'Master in bio-purification, classical Shodhana therapies, and detox regimens.'
        },
        {
            'email': 'dr.joshi@amrutam.com',
            'first_name': 'Meera',
            'last_name': 'Joshi',
            'specialization': 'NADI_PARIKSHA',
            'qualification': 'BAMS, Certified Nadi Pariksha Acharya',
            'license_number': 'AYUSH-MAH-2012-7712',
            'experience_years': 15,
            'fee': Decimal('1500.00'),
            'rating': Decimal('4.98'),
            'bio': 'Expert in Ayurvedic pulse diagnosis, early disease detection, and mind-body balance.'
        },
        {
            'email': 'dr.nair@amrutam.com',
            'first_name': 'Rajesh',
            'last_name': 'Nair',
            'specialization': 'DERMATOLOGY',
            'qualification': 'BAMS, Diploma in Ayurvedic Cosmetology & Skin Care',
            'license_number': 'AYUSH-KER-2016-3390',
            'experience_years': 9,
            'fee': Decimal('750.00'),
            'rating': Decimal('4.88'),
            'bio': 'Pioneering formulations for hair fall, scalp rejuvenation, and classical skin therapeutics.'
        }
    ]

    created_doctors = []
    for d in doctors_data:
        doc_user, u_created = User.objects.get_or_create(
            email=d['email'],
            defaults={
                'first_name': d['first_name'],
                'last_name': d['last_name'],
                'role': User.ROLE_DOCTOR,
                'is_verified': True
            }
        )
        if u_created:
            doc_user.set_password('AmrutamDoctor2026!')
            doc_user.save()

        doctor, d_created = Doctor.objects.get_or_create(
            user=doc_user,
            defaults={
                'license_number': d['license_number'],
                'specialization': d['specialization'],
                'qualification': d['qualification'],
                'experience_years': d['experience_years'],
                'consultation_fee': d['fee'],
                'rating': d['rating'],
                'total_reviews': 42,
                'bio': d['bio'],
                'is_verified': True
            }
        )
        created_doctors.append(doctor)
        print(f"  [+] Doctor ready: Dr. {doc_user.get_full_name()} ({d['specialization']})")

    # 4. Generate Availability Slots for next 5 days
    today = date.today()
    slots_created = 0
    for doctor in created_doctors:
        for day_offset in range(5):
            slot_date = today + timedelta(days=day_offset)
            # Create 4 slots per day
            times = [
                (time(9, 0), time(9, 30)),
                (time(10, 0), time(10, 30)),
                (time(14, 0), time(14, 30)),
                (time(16, 0), time(16, 30)),
            ]
            for start_t, end_t in times:
                _, s_created = AvailabilitySlot.objects.get_or_create(
                    doctor=doctor,
                    date=slot_date,
                    start_time=start_t,
                    defaults={
                        'end_time': end_t,
                        'status': AvailabilitySlot.STATUS_AVAILABLE
                    }
                )
                if s_created:
                    slots_created += 1

    print(f"  [+] Created {slots_created} doctor availability slots.")

    # 5. Create Patient User
    patient_user, p_created = User.objects.get_or_create(
        email='patient@example.com',
        defaults={
            'first_name': 'Rohan',
            'last_name': 'Verma',
            'phone_number': '+919876543210',
            'role': User.ROLE_PATIENT,
            'is_verified': True
        }
    )
    if p_created:
        patient_user.set_password('AmrutamPatient2026!')
        patient_user.save()
        profile = PatientProfile.objects.create(
            user=patient_user,
            date_of_birth=date(1995, 6, 15),
            gender='MALE',
            blood_group='O+',
            prakriti='PITTA_KAPHA'
        )
        profile.allergies = "Shellfish, Synthetic Sulfates"
        profile.chronic_conditions = "Mild Digestive Dyspepsia"
        profile.save()
        print("  [+] Created Patient: patient@example.com (Password: AmrutamPatient2026!)")

    # 6. Create Completed Consultation & Digital Prescription
    demo_slot = AvailabilitySlot.objects.filter(doctor=created_doctors[0], status=AvailabilitySlot.STATUS_AVAILABLE).first()
    if demo_slot:
        consultation = BookingService.reserve_slot(
            patient=patient_user,
            slot_id=demo_slot.id,
            chief_complaint="Excessive hair thinning and poor sleep",
            symptoms="Stress, scalp dryness, acid reflux after dinner"
        )
        # Advance payment
        payment = PaymentService.initiate_payment(consultation.id, idempotency_key=f"seed_pay_{consultation.id}")
        PaymentService.handle_payment_success(payment.gateway_order_id, f"pay_seed_{consultation.id}")

        consultation.refresh_from_db()
        consultation.status = Consultation.STATUS_COMPLETED
        consultation.started_at = demo_slot.locked_at
        consultation.ended_at = demo_slot.locked_at
        consultation.save(update_fields=['status', 'started_at', 'ended_at'])

        # Create Prescription
        rx = Prescription.objects.create(
            consultation=consultation,
            diagnosis="Pitta-Vata imbalance causing Kesha Kshaya (hair fall) and Anidra (insomnia).",
            dietary_advice="Avoid sour, pungent, and excessively spicy foods. Favor sweet fruits, cow ghee, soaked almonds.",
            lifestyle_recommendations="Abhyanga head massage with Bhringraj oil before bath; Meditative breathing (Pranayama) 15 mins daily.",
            follow_up_date=today + timedelta(days=21)
        )
        PrescriptionItem.objects.create(
            prescription=rx,
            medicine_name="Amrutam Kuntal Care Herbal Hair Oil",
            form="TAILA",
            dosage="Apply gently on scalp",
            frequency="Thrice a week",
            timing="BEFORE_MEALS",
            anupana="Warm Water",
            duration_days=30
        )
        PrescriptionItem.objects.create(
            prescription=rx,
            medicine_name="Amrutam Brakey Hair Malt & Ashwagandha Churna",
            form="AVALEHA",
            dosage="1-2 tablespoons",
            frequency="Twice daily",
            timing="AFTER_MEALS",
            anupana="Warm Milk",
            duration_days=30
        )

        sig_data = {
            'prescription_id': str(rx.id),
            'consultation_id': str(consultation.id),
            'doctor_id': str(created_doctors[0].id),
            'patient_id': str(patient_user.id),
            'diagnosis': rx.diagnosis,
            'items': [
                {'medicine_name': "Amrutam Kuntal Care Herbal Hair Oil", 'dosage': "Apply gently on scalp", 'frequency': "Thrice a week", 'duration_days': 30},
                {'medicine_name': "Amrutam Brakey Hair Malt & Ashwagandha Churna", 'dosage': "1-2 tablespoons", 'frequency': "Twice daily", 'duration_days': 30}
            ]
        }
        rx.digital_signature = generate_prescription_signature(sig_data, created_doctors[0].digital_signature_key)
        rx.signature_timestamp = consultation.updated_at
        rx.save(update_fields=['digital_signature', 'signature_timestamp'])

        print("  [+] Created sample completed consultation with signed prescription.")

    print("\n[+] Database seeding complete! Ready for local development and demonstration.")

if __name__ == '__main__':
    run()
