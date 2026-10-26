"""
Notification Service for Amrutam Telemedicine.

Handles asynchronous dispatch of:
  - Booking confirmation emails/SMS to patients
  - Appointment reminder notifications
  - Cancellation and refund notifications
  - Prescription-ready notifications

In production, integrate with AWS SES / Twilio / SendGrid.
All notification tasks are fire-and-forget Celery tasks so they never
block the critical booking or payment paths.
"""

import logging
from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
#  Async Celery Task Dispatchers                                               #
# --------------------------------------------------------------------------- #

@shared_task(
    name='apps.notifications.tasks.send_booking_confirmation',
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def send_booking_confirmation_task(self, consultation_id: str):
    """
    Sends a booking confirmation email/SMS to the patient after slot reservation.

    Retries up to 3 times with 30-second back-off if the notification provider fails.
    """
    try:
        from apps.consultations.models import Consultation
        consultation = Consultation.objects.select_related(
            'patient', 'doctor__user', 'slot'
        ).get(id=consultation_id)

        patient = consultation.patient
        doctor = consultation.doctor
        slot = consultation.slot

        message = (
            f"Dear {patient.get_full_name() or patient.email},\n\n"
            f"Your consultation with Dr. {doctor.user.get_full_name()} has been reserved.\n"
            f"Slot: {slot.start_time.strftime('%d %b %Y, %I:%M %p') if slot else 'TBD'}\n"
            f"Please complete payment within 10 minutes to confirm your booking.\n\n"
            f"Consultation ID: {consultation_id}\n"
            f"— Amrutam Ayurveda Team"
        )

        _dispatch_notification(
            recipient_email=patient.email,
            subject="Booking Reserved — Complete Payment to Confirm | Amrutam",
            message=message,
            notification_type="booking_confirmation",
            consultation_id=str(consultation_id),
        )
        logger.info("Booking confirmation sent to %s for consultation %s", patient.email, consultation_id)

    except Exception as exc:
        logger.error("Failed to send booking confirmation for %s: %s", consultation_id, exc)
        raise self.retry(exc=exc)


@shared_task(
    name='apps.notifications.tasks.send_payment_success_notification',
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def send_payment_success_notification_task(self, consultation_id: str, payment_id: str):
    """
    Sends payment confirmation and final booking confirmation to patient and doctor.
    """
    try:
        from apps.consultations.models import Consultation
        consultation = Consultation.objects.select_related(
            'patient', 'doctor__user', 'slot'
        ).get(id=consultation_id)

        patient = consultation.patient
        doctor = consultation.doctor
        slot = consultation.slot

        # Patient notification
        patient_message = (
            f"Dear {patient.get_full_name() or patient.email},\n\n"
            f"Payment confirmed! Your appointment is CONFIRMED.\n"
            f"Doctor: Dr. {doctor.user.get_full_name()}\n"
            f"Date & Time: {slot.start_time.strftime('%d %b %Y, %I:%M %p') if slot else 'TBD'}\n"
            f"Consultation ID: {consultation_id}\n"
            f"Payment Ref: {payment_id}\n\n"
            f"Join via video link 5 minutes before your appointment.\n"
            f"— Amrutam Ayurveda Team"
        )

        _dispatch_notification(
            recipient_email=patient.email,
            subject="Appointment Confirmed ✓ | Amrutam Telemedicine",
            message=patient_message,
            notification_type="payment_success",
            consultation_id=str(consultation_id),
        )

        # Doctor notification
        doctor_message = (
            f"Dr. {doctor.user.get_full_name()},\n\n"
            f"New appointment confirmed:\n"
            f"Patient: {patient.get_full_name() or patient.email}\n"
            f"Date & Time: {slot.start_time.strftime('%d %b %Y, %I:%M %p') if slot else 'TBD'}\n"
            f"Chief Complaint: {consultation.chief_complaint}\n"
            f"— Amrutam Ayurveda System"
        )

        _dispatch_notification(
            recipient_email=doctor.user.email,
            subject="New Appointment Confirmed | Amrutam Telemedicine",
            message=doctor_message,
            notification_type="doctor_appointment_confirmed",
            consultation_id=str(consultation_id),
        )

        logger.info(
            "Payment success notifications sent for consultation %s to patient %s and doctor %s",
            consultation_id, patient.email, doctor.user.email
        )

    except Exception as exc:
        logger.error("Failed to send payment success notifications for %s: %s", consultation_id, exc)
        raise self.retry(exc=exc)


@shared_task(
    name='apps.notifications.tasks.send_cancellation_notification',
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def send_cancellation_notification_task(self, consultation_id: str, reason: str, cancelled_by: str):
    """
    Notifies patient and doctor when a consultation is cancelled.
    """
    try:
        from apps.consultations.models import Consultation
        consultation = Consultation.objects.select_related(
            'patient', 'doctor__user', 'slot'
        ).get(id=consultation_id)

        patient = consultation.patient
        doctor = consultation.doctor

        message = (
            f"Dear {patient.get_full_name() or patient.email},\n\n"
            f"Your consultation (ID: {consultation_id}) has been cancelled.\n"
            f"Reason: {reason}\n"
            f"Cancelled by: {cancelled_by}\n\n"
            f"If payment was made, a refund will be initiated within 5-7 business days.\n"
            f"— Amrutam Ayurveda Team"
        )

        _dispatch_notification(
            recipient_email=patient.email,
            subject="Consultation Cancelled | Amrutam Telemedicine",
            message=message,
            notification_type="cancellation",
            consultation_id=str(consultation_id),
        )
        logger.info("Cancellation notification sent for consultation %s", consultation_id)

    except Exception as exc:
        logger.error("Failed to send cancellation notification for %s: %s", consultation_id, exc)
        raise self.retry(exc=exc)


@shared_task(
    name='apps.notifications.tasks.send_prescription_ready_notification',
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def send_prescription_ready_notification_task(self, prescription_id: str):
    """
    Notifies patient that their digital prescription is ready for download.
    """
    try:
        from apps.prescriptions.models import Prescription
        prescription = Prescription.objects.select_related(
            'consultation__patient', 'prescribed_by'
        ).get(id=prescription_id)

        patient = prescription.consultation.patient
        doctor = prescription.prescribed_by

        message = (
            f"Dear {patient.get_full_name() or patient.email},\n\n"
            f"Your prescription from Dr. {doctor.get_full_name()} is now available.\n"
            f"Prescription ID: {prescription_id}\n"
            f"You can download your prescription from the Amrutam app.\n\n"
            f"— Amrutam Ayurveda Team"
        )

        _dispatch_notification(
            recipient_email=patient.email,
            subject="Your Prescription is Ready | Amrutam Telemedicine",
            message=message,
            notification_type="prescription_ready",
            prescription_id=str(prescription_id),
        )
        logger.info("Prescription ready notification sent for prescription %s", prescription_id)

    except Exception as exc:
        logger.error("Failed to send prescription notification for %s: %s", prescription_id, exc)
        raise self.retry(exc=exc)


# --------------------------------------------------------------------------- #
#  Internal Dispatch Helper                                                    #
# --------------------------------------------------------------------------- #

def _dispatch_notification(
    recipient_email: str,
    subject: str,
    message: str,
    notification_type: str,
    **metadata,
):
    """
    Internal notification dispatcher.

    In production, integrate with AWS SES / Twilio / SendGrid using environment
    config. In development/test, logs the notification to avoid requiring
    real provider credentials.
    """
    provider = getattr(settings, 'NOTIFICATION_PROVIDER', 'log')

    if provider == 'ses':
        _send_via_ses(recipient_email, subject, message)
    elif provider == 'sendgrid':
        _send_via_sendgrid(recipient_email, subject, message)
    else:
        # Default: structured log output (works in local/CI environments)
        logger.info(
            "NOTIFICATION [%s] to=%s subject=%s metadata=%s",
            notification_type,
            recipient_email,
            subject,
            metadata
        )


def _send_via_ses(recipient_email: str, subject: str, body: str):
    """AWS SES email dispatch. Requires boto3 + SES credentials in environment."""
    try:
        import boto3
        client = boto3.client(
            'ses',
            region_name=settings.AWS_SES_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        client.send_email(
            Source=getattr(settings, 'NOTIFICATION_FROM_EMAIL', 'noreply@amrutam.com'),
            Destination={'ToAddresses': [recipient_email]},
            Message={
                'Subject': {'Data': subject},
                'Body': {'Text': {'Data': body}},
            }
        )
    except ImportError:
        logger.warning("boto3 not installed — SES notification skipped.")
    except Exception as exc:
        logger.error("SES dispatch failed: %s", exc)
        raise


def _send_via_sendgrid(recipient_email: str, subject: str, body: str):
    """SendGrid email dispatch. Requires sendgrid package + SENDGRID_API_KEY."""
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail
        sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
        mail = Mail(
            from_email=getattr(settings, 'NOTIFICATION_FROM_EMAIL', 'noreply@amrutam.com'),
            to_emails=recipient_email,
            subject=subject,
            plain_text_content=body,
        )
        sg.send(mail)
    except ImportError:
        logger.warning("sendgrid package not installed — SendGrid notification skipped.")
    except Exception as exc:
        logger.error("SendGrid dispatch failed: %s", exc)
        raise
