import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from apps.common.crypto import encrypt_phi, decrypt_phi

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'ADMIN')
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    ROLE_PATIENT = 'PATIENT'
    ROLE_DOCTOR = 'DOCTOR'
    ROLE_ADMIN = 'ADMIN'
    ROLE_AUDITOR = 'AUDITOR'

    ROLE_CHOICES = (
        (ROLE_PATIENT, 'Patient'),
        (ROLE_DOCTOR, 'Doctor'),
        (ROLE_ADMIN, 'Administrator'),
        (ROLE_AUDITOR, 'Auditor'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None
    email = models.EmailField(unique=True, db_index=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True, db_index=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_PATIENT, db_index=True)
    is_verified = models.BooleanField(default=False)
    
    # Multi-Factor Authentication
    mfa_enabled = models.BooleanField(default=False)
    mfa_secret = models.CharField(max_length=255, blank=True, null=True)

    # Auditing
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = UserManager()

    class Meta:
        indexes = [
            models.Index(fields=['email', 'role']),
        ]

    def __str__(self):
        return f"{self.email} ({self.role})"


class PatientProfile(models.Model):
    PRAKRITI_CHOICES = (
        ('VATA', 'Vata'),
        ('PITTA', 'Pitta'),
        ('KAPHA', 'Kapha'),
        ('VATA_PITTA', 'Vata-Pitta'),
        ('PITTA_KAPHA', 'Pitta-Kapha'),
        ('VATA_KAPHA', 'Vata-Kapha'),
        ('TRIDOSHA', 'Tridoshic (Balanced)'),
        ('UNKNOWN', 'Not Assessed'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile')
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, blank=True)
    blood_group = models.CharField(max_length=5, blank=True)
    emergency_contact = models.CharField(max_length=20, blank=True)
    
    # Sensitive PHI encrypted with AES-256
    _allergies_encrypted = models.TextField(blank=True, default='')
    _chronic_conditions_encrypted = models.TextField(blank=True, default='')
    
    # Ayurvedic Prakriti constitution
    prakriti = models.CharField(max_length=20, choices=PRAKRITI_CHOICES, default='UNKNOWN')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def allergies(self) -> str:
        return decrypt_phi(self._allergies_encrypted)

    @allergies.setter
    def allergies(self, val: str):
        self._allergies_encrypted = encrypt_phi(val)

    @property
    def chronic_conditions(self) -> str:
        return decrypt_phi(self._chronic_conditions_encrypted)

    @chronic_conditions.setter
    def chronic_conditions(self, val: str):
        self._chronic_conditions_encrypted = encrypt_phi(val)

    def __str__(self):
        return f"PatientProfile({self.user.email})"
