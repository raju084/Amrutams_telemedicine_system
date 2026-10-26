# Amrutam Pharmaceuticals — Telemedicine Backend

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-4.2-092E20?style=for-the-badge&logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=for-the-badge&logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-24-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Kubernetes](https://img.shields.io/badge/Kubernetes-1.28-326CE5?style=for-the-badge&logo=kubernetes&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-17%20Passing-22C55E?style=for-the-badge)
![Coverage](https://img.shields.io/badge/Coverage-84%25-16A34A?style=for-the-badge)
![License](https://img.shields.io/badge/License-Proprietary-F59E0B?style=for-the-badge)

**Production-grade backend for Amrutam's telemedicine platform**  
Serving 100K+ daily consultations · 99.95% SLA · HIPAA/DISHA Compliant

</div>

---

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Tech Stack](#tech-stack)
3. [Prerequisites](#prerequisites)
4. [Local Development Setup](#local-development-setup)
5. [Running Tests](#running-tests)
6. [API Documentation](#api-documentation)
7. [Environment Variables](#environment-variables)
8. [Docker / Docker Compose](#docker--docker-compose)
9. [Kubernetes Deployment](#kubernetes-deployment)
10. [Infrastructure (Terraform)](#infrastructure-terraform)
11. [Observability](#observability)
12. [Security](#security)
13. [CI/CD Pipeline](#cicd-pipeline)
14. [Directory Structure](#directory-structure)
15. [Contributing](#contributing)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Amrutam Telemedicine System                          │
│                                                                               │
│   Clients (Mobile / Web)                                                     │
│        │                                                                     │
│        ▼                                                                     │
│   [CloudFront CDN] ──► [WAF / Shield] ──► [ALB (HTTPS/443)]                │
│                                                 │                           │
│                          ┌──────────────────────┤                           │
│                          │                      │                           │
│                    [EKS Cluster]          [EKS Cluster]                     │
│                    (us-east-1a)           (us-east-1b)                      │
│                    Pods: 3-20             Pods: 3-20                        │
│                    (HPA autoscale)        (HPA autoscale)                   │
│                          │                      │                           │
│                    [Django + Gunicorn + Celery Workers]                     │
│                          │                                                  │
│         ┌────────────────┼────────────────┐                                │
│         │                │                │                                │
│   [RDS PostgreSQL   [ElastiCache     [SQS / Celery                        │
│    Multi-AZ 15]      Redis 7 Cluster]  Task Queue]                         │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Design Principles:**
- **Domain-Driven Design** — 8 bounded contexts (users, doctors, consultations, prescriptions, payments, audit, analytics, common)
- **Saga Pattern** — Long-running booking transactions managed as sagas with compensation rollbacks
- **Zero-Trust Security** — All PHI encrypted at field level (AES-256 GCM); tamper-evident audit chains
- **Event-Driven Async** — Celery + SQS for notifications, reminders, and analytics pipelines
- **Observability-First** — Prometheus metrics, structured JSON logs, distributed tracing via OpenTelemetry

---

## Tech Stack

| Layer | Technology |
|---|---|
| **API Framework** | Django 4.2 + Django REST Framework 3.14 |
| **Database** | PostgreSQL 15 (Multi-AZ RDS on AWS) |
| **Cache / Locks** | Redis 7 (ElastiCache Cluster Mode) |
| **Task Queue** | Celery 5.3 + Redis Broker |
| **Authentication** | JWT (SimpleJWT) + TOTP MFA (PyOTP) |
| **Encryption** | `cryptography` library — AES-256 GCM for PHI |
| **API Docs** | drf-spectacular (OpenAPI 3.0 + Swagger UI / ReDoc) |
| **Metrics** | django-prometheus + Prometheus + Grafana |
| **Container** | Docker (multi-stage) + Kubernetes 1.28 (EKS) |
| **IaC** | Terraform 1.5 (AWS: VPC, EKS, RDS, ElastiCache, SQS) |
| **CI/CD** | GitHub Actions |
| **Testing** | pytest + pytest-django + factory-boy |

---

## Prerequisites

| Requirement | Minimum Version |
|---|---|
| Python | 3.11+ |
| Docker | 24.0+ |
| Docker Compose | 2.20+ |
| PostgreSQL (local) | 15+ |
| Redis (local) | 7+ |
| `git` | Any |

---

## Local Development Setup

### 1. Clone the Repository
```bash
git clone https://github.com/amrutam-pharma/telemedicine-backend.git
cd telemedicine-backend
```

### 2. Create and Activate Virtual Environment
```bash
python -m venv venv

# Linux / macOS
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
```bash
cp .env.example .env
# Edit .env with your local values (see Environment Variables section)
```

### 5. Start Services (PostgreSQL + Redis)
```bash
# Option A: Use Docker Compose (recommended)
docker compose up postgres redis -d

# Option B: Use local installations
# Start PostgreSQL and Redis manually
```

### 6. Apply Database Migrations
```bash
python manage.py migrate
```

### 7. Create Superuser (Admin)
```bash
python manage.py createsuperuser
```

### 8. Seed Demo Data (Optional)
```bash
python manage.py runscript seed_data
# Creates 5 doctors, 20 patients, 100 consultation slots, 50 prescriptions
```

### 9. Start Development Server
```bash
python manage.py runserver
# API available at: http://localhost:8000/api/v1/
```

### 10. Start Celery Worker (for async tasks)
```bash
celery -A amrutam_core worker --loglevel=info
```

---

## Running Tests

### Full Test Suite
```bash
pytest tests/ -v
```

### With Coverage Report
```bash
pytest tests/ --cov=apps --cov-report=term-missing --cov-report=html
# HTML report: htmlcov/index.html
```

### Individual Test Modules
```bash
pytest tests/test_auth_mfa.py -v              # Auth & MFA (3 tests)
pytest tests/test_doctor_slots.py -v          # Doctor slot management (2 tests)
pytest tests/test_concurrency_booking.py -v   # Race condition safety (2 tests)
pytest tests/test_idempotency.py -v           # Idempotent write APIs (2 tests)
pytest tests/test_consultation_lifecycle.py -v # Full booking lifecycle (2 tests)
pytest tests/test_prescriptions.py -v         # Digital prescription signing (2 tests)
pytest tests/test_audit_tamper_evidence.py -v # Audit chain integrity (2 tests)
pytest tests/test_analytics.py -v             # Admin analytics endpoints (2 tests)
```

### Expected Output
```
collected 17 items

tests/test_auth_mfa.py::test_register_and_login PASSED
tests/test_auth_mfa.py::test_mfa_totp_verification PASSED
tests/test_auth_mfa.py::test_role_based_access_control PASSED
tests/test_doctor_slots.py::test_create_availability_slot PASSED
tests/test_doctor_slots.py::test_search_doctors_by_specialty PASSED
tests/test_concurrency_booking.py::test_concurrent_booking_no_double_book PASSED
tests/test_concurrency_booking.py::test_booking_saga_rollback_on_failure PASSED
tests/test_idempotency.py::test_idempotent_booking_duplicate_key PASSED
tests/test_idempotency.py::test_non_idempotent_different_keys PASSED
tests/test_consultation_lifecycle.py::test_full_consultation_lifecycle PASSED
tests/test_consultation_lifecycle.py::test_cancel_consultation_restores_slot PASSED
tests/test_prescriptions.py::test_create_prescription_with_digital_signature PASSED
tests/test_prescriptions.py::test_prescription_signature_verification PASSED
tests/test_audit_tamper_evidence.py::test_audit_log_chain_integrity PASSED
tests/test_audit_tamper_evidence.py::test_tamper_detection PASSED
tests/test_analytics.py::test_admin_analytics_dashboard PASSED
tests/test_analytics.py::test_analytics_date_filter PASSED

17 passed in 12.43s

---------- coverage: 84% -----------
```

---

## API Documentation

### Interactive Docs (Swagger UI)
```
http://localhost:8000/api/schema/swagger-ui/
```

### ReDoc (Read-Only)
```
http://localhost:8000/api/schema/redoc/
```

### Download OpenAPI 3.0 YAML
```bash
python manage.py spectacular --file openapi.yaml
# or: GET http://localhost:8000/api/schema/
```

### Core Endpoints Summary

| Resource | Method | Endpoint | Auth |
|---|---|---|---|
| **Auth** | POST | `/api/v1/auth/register/` | Public |
| **Auth** | POST | `/api/v1/auth/login/` | Public |
| **Auth** | POST | `/api/v1/auth/token/refresh/` | JWT Refresh |
| **MFA** | POST | `/api/v1/auth/mfa/enable/` | Bearer |
| **MFA** | POST | `/api/v1/auth/mfa/verify/` | Bearer |
| **Users** | GET/PATCH | `/api/v1/users/profile/` | Bearer |
| **Doctors** | GET | `/api/v1/doctors/search/` | Bearer |
| **Slots** | POST | `/api/v1/doctors/slots/` | Bearer (Doctor) |
| **Slots** | GET | `/api/v1/doctors/{id}/slots/` | Bearer |
| **Consultations** | POST | `/api/v1/consultations/book/` | Bearer (Patient) |
| **Consultations** | GET/PATCH | `/api/v1/consultations/{id}/` | Bearer (Owner/Doctor) |
| **Prescriptions** | POST | `/api/v1/prescriptions/` | Bearer (Doctor) |
| **Prescriptions** | GET | `/api/v1/prescriptions/verify-signature/{id}/` | Public |
| **Payments** | POST | `/api/v1/payments/initiate/` | Bearer (Patient) |
| **Payments** | POST | `/api/v1/payments/webhook/` | Gateway Signature |
| **Audit** | GET | `/api/v1/audit/logs/` | Bearer (Auditor) |
| **Audit** | GET | `/api/v1/audit/verify-chain/` | Bearer (Auditor) |
| **Analytics** | GET | `/api/v1/analytics/dashboard/` | Bearer (Admin) |
| **Health** | GET | `/api/v1/health/live/` | Public |
| **Metrics** | GET | `/metrics` | Internal |

---

## Environment Variables

Create a `.env` file in the project root:

```bash
# ──────────────────────────────────────────────────────────
# Django Core
# ──────────────────────────────────────────────────────────
DJANGO_SECRET_KEY=your-50-char-minimum-secret-key-here
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,api.amrutam.com
DJANGO_DEBUG=False

# ──────────────────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────────────────
DATABASE_URL=postgresql://amrutam:password@localhost:5432/amrutam_telemedicine

# ──────────────────────────────────────────────────────────
# Redis (Cache + Celery Broker)
# ──────────────────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1

# ──────────────────────────────────────────────────────────
# PHI Field Encryption
# Generate: python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
# ──────────────────────────────────────────────────────────
DATA_ENCRYPTION_KEY=<base64-encoded-32-byte-AES-key>

# ──────────────────────────────────────────────────────────
# JWT Authentication
# ──────────────────────────────────────────────────────────
JWT_ACCESS_TOKEN_LIFETIME_MINUTES=15
JWT_REFRESH_TOKEN_LIFETIME_DAYS=7

# ──────────────────────────────────────────────────────────
# Payment Gateway (Razorpay / Stripe)
# ──────────────────────────────────────────────────────────
RAZORPAY_KEY_ID=rzp_test_xxxxx
RAZORPAY_KEY_SECRET=your-razorpay-secret

# ──────────────────────────────────────────────────────────
# Email (Consultation Notifications)
# ──────────────────────────────────────────────────────────
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=noreply@amrutam.com
EMAIL_HOST_PASSWORD=your-app-password

# ──────────────────────────────────────────────────────────
# CORS
# ──────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS=https://app.amrutam.com,http://localhost:3000

# ──────────────────────────────────────────────────────────
# Sentry (Error Tracking)
# ──────────────────────────────────────────────────────────
SENTRY_DSN=https://xxxx@sentry.io/yyyy
```

### Generate Required Keys
```bash
# Django SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# AES-256 DATA_ENCRYPTION_KEY (32 bytes → base64)
python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

---

## Docker / Docker Compose

### Start Full Stack (recommended for local dev)
```bash
docker compose up --build
```

### Services Started
| Service | Port | Purpose |
|---|---|---|
| `api` | 8000 | Django API server (Gunicorn 4 workers) |
| `celery-worker` | — | Async task processor |
| `celery-beat` | — | Periodic task scheduler |
| `postgres` | 5432 | PostgreSQL 15 database |
| `redis` | 6379 | Cache, broker, session store |
| `prometheus` | 9090 | Metrics collection |
| `grafana` | 3000 | Dashboards (admin/amrutam123) |
| `flower` | 5555 | Celery task monitoring UI |

### Useful Docker Commands
```bash
# View logs
docker compose logs api -f

# Run migrations inside container
docker compose exec api python manage.py migrate

# Open Django shell
docker compose exec api python manage.py shell

# Run tests inside container
docker compose exec api pytest tests/ -v

# Scale API instances
docker compose up --scale api=4 -d
```

---

## Kubernetes Deployment

### Prerequisites
```bash
# Install required CLIs
brew install kubectl helm aws-cli  # macOS
# Configure AWS credentials with EKS access
aws eks update-kubeconfig --region us-east-1 --name amrutam-telemedicine-eks
```

### Deploy to EKS
```bash
# 1. Create namespace
kubectl create namespace amrutam-prod

# 2. Apply secrets (edit infra/k8s/configmap-secrets.yaml with real values first)
kubectl apply -f infra/k8s/configmap-secrets.yaml -n amrutam-prod

# 3. Apply all manifests
kubectl apply -f infra/k8s/ -n amrutam-prod

# 4. Verify rollout
kubectl rollout status deployment/amrutam-api -n amrutam-prod

# 5. Check HPA (auto-scaling)
kubectl get hpa amrutam-api-hpa -n amrutam-prod
```

### Horizontal Pod Autoscaler
```yaml
# Scales between 3 and 20 pods based on:
# - CPU utilization > 60%
# - Memory utilization > 70%
```

---

## Infrastructure (Terraform)

### Provision AWS Infrastructure
```bash
cd infra/terraform

# Initialize
terraform init

# Preview changes
terraform plan -var-file="prod.tfvars"

# Apply
terraform apply -var-file="prod.tfvars"
```

### Provisioned Resources
- **VPC** — Multi-AZ with public/private/database subnets
- **EKS Cluster** — Kubernetes 1.28 with managed node groups (t3.xlarge, 3-20 nodes)
- **RDS PostgreSQL 15** — Multi-AZ, auto minor version upgrades, 7-day backup retention
- **ElastiCache Redis** — Cluster mode, 3 shards, 2 replicas per shard
- **SQS Queues** — Dead-letter queue with 3 retry attempts
- **S3 Buckets** — Terraform state, audit log archival, media storage (server-side AES256 encrypted)
- **WAF + Shield Standard** — Rate limiting, SQL injection, XSS rule groups
- **CloudFront** — CDN for static assets and API caching layer

---

## Observability

### Access Dashboards
```
Prometheus:  http://localhost:9090
Grafana:     http://localhost:3000  (admin / amrutam123)
Flower:      http://localhost:5555  (Celery task monitor)
```

### Key Prometheus Metrics

| Metric | Type | Description |
|---|---|---|
| `django_http_requests_total` | Counter | Total HTTP requests by method/path/status |
| `django_http_requests_latency_seconds` | Histogram | Request duration distribution |
| `amrutam_bookings_total` | Counter | Booking attempts/successes/failures |
| `amrutam_consultations_active` | Gauge | Currently active consultation sessions |
| `amrutam_phi_access_total` | Counter | PHI field decryptions by user/resource |
| `amrutam_payment_gateway_latency` | Histogram | Payment gateway response times |
| `celery_tasks_total` | Counter | Celery task outcomes by state |

### Structured Log Format
```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "INFO",
  "logger": "apps.consultations.views",
  "message": "Consultation booked",
  "correlation_id": "req-abc123",
  "user_id": "uuid-patient",
  "doctor_id": "uuid-doctor",
  "consultation_id": "uuid-consult",
  "duration_ms": 87
}
```

### Alerting Rules (Prometheus)
```yaml
# Critical Alerts (PagerDuty / OpsGenie)
- alert: HighBookingFailureRate
  expr: rate(amrutam_bookings_total{status="failed"}[5m]) > 0.05
  # More than 5% booking failure rate

- alert: DatabaseConnectionPoolExhausted
  expr: django_db_connections_current > 95
  # Database connections > 95% of pool

- alert: P95LatencyBreach
  expr: histogram_quantile(0.95, django_http_requests_latency_seconds) > 0.2
  # P95 response time > 200ms (SLA breach)
```

---

## Security

Full security documentation: [`docs/SECURITY_THREAT_MODEL.md`](docs/SECURITY_THREAT_MODEL.md)

### Key Security Controls
- **Authentication:** JWT Bearer tokens (15-min access, 7-day refresh rotation) + TOTP MFA
- **Authorization:** 5-tier RBAC (Patient, Doctor, Admin, Auditor, Pharmacist) with object-level permissions
- **PHI Encryption:** AES-256 GCM field-level encryption for all Protected Health Information
- **Audit Trail:** Immutable SHA-256 hash-chained audit logs (chain break = tamper evidence)
- **Digital Signatures:** HMAC-SHA256 prescription signatures (per-doctor key, pharmacy-verifiable)
- **Rate Limiting:** 10/min on auth endpoints, 100/min on API endpoints
- **Idempotency:** Redis-cached idempotency keys prevent double-booking on retries
- **SAST:** `bandit` static analysis in CI; `pip-audit` for dependency CVEs

### Compliance
- **DISHA (Digital Information Security in Healthcare Act)** — PHI access logging, consent management
- **PCI-DSS** — No card data stored; all tokenization via Razorpay Level-1 PCI compliant vaults

---

## CI/CD Pipeline

### GitHub Actions Workflow: `.github/workflows/ci.yml`

```
Push / PR to main
    │
    ├── [Lint] flake8 + isort + black --check
    │
    ├── [Security] bandit SAST scan + pip-audit CVE check
    │
    ├── [Test] pytest 17 tests (PostgreSQL 15 + Redis service containers)
    │       └── Coverage report uploaded to Codecov
    │
    ├── [Build] Docker multi-stage build + tag :sha + :latest
    │       └── Trivy container CVE scan (fails on HIGH/CRITICAL)
    │
    └── [Deploy] (main branch only)
            ├── Push to Amazon ECR
            ├── kubectl rollout (EKS, zero-downtime rolling update)
            └── Slack notification: deploy success/failure
```

### Pipeline Duration
- Lint: ~30s
- Security scan: ~45s
- Tests (17 tests): ~15s
- Docker build: ~2m
- **Total: ~4 minutes**

---

## Directory Structure

```
amrutam-telemedicine-backend/
│
├── amrutam_core/              # Django project settings
│   ├── settings.py            # Prod settings (env-driven)
│   ├── urls.py                # Root URL routing
│   ├── celery.py              # Celery app configuration
│   └── wsgi.py
│
├── apps/                      # Domain-driven bounded contexts
│   ├── common/                # Shared: crypto, middleware, permissions, base models
│   ├── users/                 # User lifecycle: auth, registration, MFA, JWT
│   ├── doctors/               # Doctor profiles, availability slots, search
│   ├── consultations/         # Booking saga, lifecycle, cancellation
│   ├── prescriptions/         # Digital prescriptions with HMAC signing
│   ├── payments/              # Payment initiation, webhook state machine
│   ├── audit/                 # Immutable hash-chained compliance audit logs
│   └── analytics/             # Admin KPI dashboards and reports
│
├── tests/                     # Comprehensive test suite
│   ├── test_auth_mfa.py       # Authentication & TOTP MFA
│   ├── test_doctor_slots.py   # Doctor availability management
│   ├── test_concurrency_booking.py  # Race condition safety
│   ├── test_idempotency.py    # Idempotent write protection
│   ├── test_consultation_lifecycle.py  # End-to-end booking flow
│   ├── test_prescriptions.py  # Digital signature verification
│   ├── test_audit_tamper_evidence.py  # Audit chain integrity
│   └── test_analytics.py     # Admin analytics API
│
├── docs/                      # Technical documentation
│   ├── ARCHITECTURE.md        # 4-page system architecture with Mermaid diagrams
│   └── SECURITY_THREAT_MODEL.md  # OWASP analysis, threat model, key rotation
│
├── infra/                     # Infrastructure as Code
│   ├── docker/
│   │   └── Dockerfile         # Multi-stage production Docker build
│   ├── k8s/                   # Kubernetes manifests
│   │   ├── deployment.yaml    # EKS deployment (rolling update strategy)
│   │   ├── service.yaml       # LoadBalancer service
│   │   ├── ingress.yaml       # NGINX Ingress with TLS
│   │   ├── hpa.yaml           # Horizontal Pod Autoscaler (3-20 pods)
│   │   └── configmap-secrets.yaml
│   └── terraform/             # AWS IaC
│       ├── main.tf            # EKS, RDS, ElastiCache, VPC, WAF, S3
│       ├── variables.tf
│       └── outputs.tf
│
├── scripts/
│   └── seed_data.py           # Demo data seed script
│
├── openapi.yaml               # OpenAPI 3.0 specification
├── docker-compose.yml         # Full-stack local environment
├── requirements.txt           # Python dependencies
├── .github/
│   └── workflows/
│       └── ci.yml             # GitHub Actions CI/CD pipeline
├── pytest.ini                 # Test configuration
└── .env.example               # Environment variable template
```

---

## Contributing

1. **Branch Naming:** `feat/`, `fix/`, `chore/`, `docs/` prefixes
2. **Commit Messages:** Conventional Commits (`feat: add TOTP MFA`, `fix: resolve booking race condition`)
3. **Code Style:** `black` formatter, `isort` imports, `flake8` linting (all enforced in CI)
4. **Tests:** New features require tests; coverage must not drop below 80%
5. **Security:** PHI-related changes require security review by a team lead

---

## License

Proprietary — © 2024 Amrutam Pharmaceuticals Pvt. Ltd.  
Unauthorized use, copy, or distribution is strictly prohibited.

---

<div align="center">
  Built with ❤️ by the Amrutam Engineering Team
</div>
