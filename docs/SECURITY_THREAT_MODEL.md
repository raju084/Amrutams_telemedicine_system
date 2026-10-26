# Amrutam Telemedicine Backend — Security Checklist & Threat Model

## 1. OWASP Top 10 Mitigation Matrix

| OWASP 2021 Risk | Severity | Amrutam Mitigation | Status |
|---|---|---|---|
| **A01 - Broken Access Control** | Critical | JWT Bearer Auth, Role-Based permissions (IsPatient, IsDoctor, IsAdmin, IsAuditor), object-level `IsOwnerOrDoctorOrAdmin` for all consultation reads | Mitigated |
| **A02 - Cryptographic Failures** | Critical | Field-level AES-256 GCM encryption for all PHI fields (allergies, symptoms); HMAC-SHA256 prescription digital signatures; TLS 1.3 enforced; secrets via env vars, never hardcoded | Mitigated |
| **A03 - Injection** | High | Django ORM parameterized queries (zero raw SQL); DRF serializer input validation; strict type coercion | Mitigated |
| **A04 - Insecure Design** | High | Threat-modelled Saga architecture; distributed locking to prevent TOCTOU race conditions; idempotency keys for all write operations | Mitigated |
| **A05 - Security Misconfiguration** | High | `DEBUG=False` in production; non-root Docker user (UID 10001); `X-Frame-Options: DENY`; `Strict-Transport-Security`; secret rotation via AWS Secrets Manager | Mitigated |
| **A06 - Vulnerable & Outdated Components** | Medium | `bandit` static analysis in CI pipeline; Dependabot auto-PRs for security patches; pinned `requirements.txt` | Mitigated |
| **A07 - Identity & Auth Failures** | Critical | TOTP MFA (RFC 6238) via PyOTP; JWT blacklisting on logout/refresh rotation; brute-force rate limiting (10/min on auth endpoints); password minimum 10 chars via Django validators | Mitigated |
| **A08 - Software & Data Integrity** | High | Tamper-evident SHA-256 hash-chained audit logs; prescription HMAC-SHA256 digital signatures; Docker image SHA digest pinning in CI | Mitigated |
| **A09 - Logging & Monitoring Failures** | Medium | Structured JSON logging with correlation IDs; Prometheus metrics; Grafana dashboards; immutable AuditLog model prevents deletion | Mitigated |
| **A10 - SSRF** | Medium | No outbound user-controlled URL traversal in core flows; payment gateway callback IPs allowlisted; Django ALLOWED_HOSTS enforced | Mitigated |

---

## 2. Attack Surface Analysis

### 2.1 External Entry Points

| Attack Surface | Exposure | Protection Mechanism |
|---|---|---|
| `POST /api/v1/auth/login/` | Public | Rate limiting (10/min per IP), brute-force lockout, no username enumeration (constant-time response) |
| `POST /api/v1/auth/register/` | Public | Input validation, password strength enforcement, email uniqueness constraint |
| `POST /api/v1/payments/webhook/` | Public (Gateway IPs) | IP allowlist in NGINX/WAF; webhook payload signature verification (HMAC); idempotent state machine |
| `GET /api/v1/prescriptions/{id}/verify-signature/` | Public (Pharmacy) | Read-only endpoint, zero database writes, no authentication required |
| `GET /api/v1/health/live/` | Public | Returns 200 only — no sensitive data exposed |
| `GET /metrics` | Internal Only | Exposed on internal cluster network only; not reachable from public internet |
| Admin Django Panel `/admin/` | Internal VPN Only | Staff-only access; MFA enforced; read-only for AuditLog model |

### 2.2 PHI Data Boundaries (Protected Health Information)

All fields marked below are encrypted **at-rest with AES-256 GCM** (field-level encryption before PostgreSQL persistence):

| Model | Sensitive PHI Fields | Encryption |
|---|---|---|
| `PatientProfile` | `_allergies_encrypted`, `_chronic_conditions_encrypted` | AES-256 GCM (field-level) |
| `Consultation` | `_symptoms_encrypted` | AES-256 GCM (field-level) |
| `Prescription` | `diagnosis`, `dietary_advice` | Plain DB text (non-PHI, patient-consented) |
| `Payment` | `gateway_payment_id` | Plain DB (no PAN/card data stored; tokenized via gateway) |

> **PCI-DSS Note:** Raw card numbers, CVV, and bank account details are **never transmitted through or stored in Amrutam systems**. All payment tokenization is entirely managed by Razorpay/Stripe on their PCI-DSS Level 1 compliant servers.

---

## 3. Data Classification

| Classification | Examples | Storage | Transmission |
|---|---|---|---|
| **PHI - Top Secret** | Allergies, chronic conditions, consultation symptoms | AES-256 GCM encrypted fields in PostgreSQL | TLS 1.3 only |
| **Sensitive - Confidential** | User email, phone, DOB, prakriti | Hashed passwords (bcrypt), plaintext email | TLS 1.3 only |
| **Internal - Restricted** | Doctor license numbers, prescription contents, HMAC keys | Plaintext PostgreSQL (encrypted volume) | TLS 1.3 only |
| **Public** | Doctor names, specializations, consultation fees, availability dates | Plaintext PostgreSQL | HTTPS / CDN cacheable |
| **Audit Trail** | IP addresses, user actions, correlation IDs | Append-only SHA-256 hash-chained AuditLog | Internal only |

---

## 4. Encryption Architecture

### 4.1 Data-at-Rest Encryption
```
PatientProfile.allergies (plaintext)
    -> encrypt_phi(plaintext)
        -> AESGCM(32-byte key).encrypt(12-byte nonce, plaintext.encode())
        -> base64.b64encode(nonce + ciphertext + GCM_auth_tag)
        -> stored in PatientProfile._allergies_encrypted (DB field)

Decryption path:
    PatientProfile._allergies_encrypted (DB field)
        -> base64.b64decode()
        -> nonce = raw[:12], ciphertext = raw[12:]
        -> AESGCM(key).decrypt(nonce, ciphertext, None)
        -> plaintext
```

### 4.2 Prescription Digital Signature (Tamper-Proof Integrity)
```
Prescription Payload (canonical JSON) + Doctor HMAC Secret
    -> HMAC-SHA256(canonical_payload, doctor.digital_signature_key)
    -> 64-character hexdigest stored as Prescription.digital_signature

Verification (Pharmacy / Public):
    GET /api/v1/prescriptions/{id}/verify-signature/
    -> Reconstruct canonical payload from DB (sorted items)
    -> HMAC-SHA256(payload, doctor.digital_signature_key)
    -> hmac.compare_digest(computed, stored) -> True/False
```

### 4.3 Key Rotation Protocol
```
1. Generate new DATA_ENCRYPTION_KEY via:
   python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"

2. Deploy new key to AWS Secrets Manager as DATA_ENCRYPTION_KEY_V2

3. Run key rotation migration job (re-encrypts all PHI fields with new key)

4. Retire old key after 100% re-encryption verification
   
5. Rotate doctor digital_signature_key independently per quarter:
   Doctor.objects.update(digital_signature_key=secrets.token_hex(32))
```

---

## 5. Audit Log Integrity Mechanism

The `AuditLog` table enforces a **SHA-256 hash chain** (similar to blockchain linkage):

```python
# Each new log entry chains from the previous entry's hash
log.previous_log_hash = last_log.log_hash  # or "GENESIS_ROOT_HASH"
log.log_hash = SHA256({
    'prev_hash': previous_log_hash,
    'user_id': user_id,
    'action': action,
    'resource_type': resource_type,
    'resource_id': resource_id,
    'payload': payload_diff
})
# Once saved, model.save() raises PermissionDenied if called again (immutable)
# model.delete() raises PermissionDenied unconditionally
```

**Chain Verification:** Compliance officers call `GET /api/v1/audit/verify-chain/` which re-traverses all records, recomputes hashes, and reports any broken links indicating data tampering or unauthorized deletions.

---

## 6. Dependency Security Scanning

```yaml
# .github/workflows/ci.yml (Security stage)
- name: SAST Security Scan (Bandit)
  run: bandit -r apps -ll  # Fails on Medium+ severity issues

- name: Dependency Vulnerability Check (Safety / pip-audit)
  run: pip-audit -r requirements.txt --ignore-vuln PYSEC-2022-xxxx

- name: Container Image CVE Scan (Trivy)
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: amrutam/telemedicine-backend:latest
    exit-code: 1
    severity: HIGH,CRITICAL
```

---

## 7. Security Response Playbook

| Incident | Detection | Response |
|---|---|---|
| **Brute-force login** | Rate limiter triggers 429; Prometheus alert `auth_failure_rate > 50/min` | Temporary IP-level block via WAF; Security notification to admin |
| **JWT Token Theft** | Anomalous concurrent sessions from different geo-IPs | Force-invalidate token family in blacklist; user forced to re-authenticate + MFA |
| **PHI Data Breach** | Database audit log shows unauthorized `SELECT` queries | Immediate partition isolation; DISHA 72-hour breach notification triggered |
| **Prescription Tampering** | Signature verification returns `False` | Alert pharmacies to reject affected prescription batch; revoke doctor's digital key |
| **Audit Chain Break** | `verify-chain` endpoint returns `COMPROMISED` | Forensic snapshot of database; escalate to CISO; restore from verified S3 WAL backup |
| **Dependency Vulnerability** | `pip-audit` or Dependabot alert | Patch within 48h for Critical, 7 days for High; CI pipeline rejects deploys with known vulns |
