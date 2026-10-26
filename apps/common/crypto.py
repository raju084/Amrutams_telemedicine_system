import os
import base64
import hmac
import hashlib
import json
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings

def get_encryption_key() -> bytes:
    """
    Retrieves or derives the 256-bit AES-GCM encryption key.
    """
    key_str = getattr(settings, 'DATA_ENCRYPTION_KEY', '')
    try:
        raw_key = base64.b64decode(key_str)
        if len(raw_key) == 32:
            return raw_key
    except Exception:
        pass
    # Deterministic SHA-256 fallback if key string is non-base64
    return hashlib.sha256(key_str.encode()).digest()


def encrypt_phi(plaintext: str) -> str:
    """
    Encrypts sensitive Protected Health Information (PHI) using AES-256 GCM.
    Returns base64 encoded string: nonce (12 bytes) + ciphertext + tag.
    """
    if not plaintext:
        return ""
    key = get_encryption_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
    return base64.b64encode(nonce + ciphertext).decode('utf-8')


def decrypt_phi(encrypted_text: str) -> str:
    """
    Decrypts AES-256 GCM encrypted health notes / PHI text.
    """
    if not encrypted_text:
        return ""
    try:
        raw = base64.b64decode(encrypted_text)
        if len(raw) < 28:
            return encrypted_text  # Not valid ciphertext, return as is
        nonce = raw[:12]
        ciphertext = raw[12:]
        key = get_encryption_key()
        aesgcm = AESGCM(key)
        decrypted = aesgcm.decrypt(nonce, ciphertext, None)
        return decrypted.decode('utf-8')
    except Exception:
        # Fallback in case of raw unencrypted legacy values
        return encrypted_text


def generate_prescription_signature(prescription_data: dict, doctor_secret: str) -> str:
    """
    Generates a cryptographically secure HMAC-SHA256 signature for a prescription
    to ensure it cannot be forged or tampered with.
    """
    canonical_payload = json.dumps(prescription_data, sort_keys=True, separators=(',', ':'))
    signature = hmac.new(
        doctor_secret.encode('utf-8'),
        canonical_payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature


def verify_prescription_signature(prescription_data: dict, doctor_secret: str, signature: str) -> bool:
    """
    Verifies the HMAC-SHA256 signature against prescription payload.
    """
    expected = generate_prescription_signature(prescription_data, doctor_secret)
    return hmac.compare_digest(expected, signature)
