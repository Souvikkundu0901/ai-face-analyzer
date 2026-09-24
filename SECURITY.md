# 🛡️ Security Policy & Architecture

This document outlines the security architecture, data privacy model, vulnerability disclosure process, and defense-in-depth measures implemented in the **AI Face Analyzer** project.

---

## 1. Supported Versions

Security updates, bug fixes, and vulnerability patches are actively maintained for the following versions:

| Version | Supported | Notes |
| :--- | :---: | :--- |
| **`v0.5.x`** | ✅ **Yes** | Current release (Production Hardened, Rate-limited, Alembic migrations) |
| `v0.4.x` | ⚠️ Security fixes only | Auth, DB persistence & longitudinal comparison |
| `< v0.4.0` | ❌ No | Legacy development prototypes |

---

## 2. Reporting a Vulnerability

We take the security and privacy of our users and their biometric data seriously. If you discover a security vulnerability or potential flaw, please report it responsibly:

* 📧 **Security Contact**: Reach out directly via GitHub Issues (private security advisory) or contact the project maintainer at [souvikkundu19@gmail.com](mailto:souvikkundu19@gmail.com).
* ⏱️ **Response SLA**: You will receive an initial response within **48 hours** acknowledging receipt of your report.
* 🔒 **Coordinated Disclosure**: Please allow up to **14 business days** for a patch to be developed and deployed before public disclosure.

Please include the following details in your report:
* Description of the vulnerability and potential impact.
* Step-by-step reproduction instructions or a minimal Proof of Concept (PoC).
* Any affected components, endpoints, or dependencies.

---

## 3. Security Architecture & Threat Mitigations

The application employs a layered defense-in-depth security model:

```
[ Incoming Request ]
         │
         ▼
[ Rate Limiting Middleware ] ──► (429 Too Many Requests if > limit)
         │
         ▼
[ CORS Origin Verification ] ──► (Reject unauthorized origins)
         │
         ▼
[ Binary Magic Byte Sniffing ] ──► (400 Bad Request if spoofed/corrupt)
[ Max Payload Size Enforcement ] ──► (413 Content Too Large if > 10MB)
         │
         ▼
[ JWT Authentication Guard ] ──► (401 Unauthorized if invalid/expired)
         │
         ▼
[ In-Memory Pipeline Execution ] ──► (Raw Image destroyed immediately)
         │
         ▼
[ Data Layer & Isolation ] ──► (Multi-tenant scoped by user_id)
```

---

### A. Strict Zero-Image Retention Privacy Model
* **Ephemeral Processing**: Selfie images uploaded for analysis are processed **strictly in-memory** and discarded immediately after feature extraction.
* **No Disk Persistence**: Raw image buffers are never written to disk, object storage, or cloud buckets.
* **Derived Metrics Only**: The database persists only derived mathematical metrics (aspect ratios, color space statistics, high-frequency gradient scores, triggered rule IDs).
* **Zero PII Error Tracking**: Sentry exception tracking is configured with `send_default_pii = False` to prevent user biometric data or payload buffers from leaking to external monitoring services.

---

### B. Authentication & Session Security
* **Password Hashing**: Plaintext passwords are salted and hashed using direct **`bcrypt`** (work factor 12).
* **Short-Lived Access Tokens**: HMAC-SHA256 JWT access tokens expire after **60 minutes** (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`).
* **DB-Backed Single-Use Refresh Token Rotation**:
  * Refresh tokens are stored as **SHA-256 hashes** (`token_hash`) in the database.
  * Every refresh request invalidates and consumes the submitted token, issuing a new access/refresh pair.
  * **Replay & Theft Detection**: Presenting an already-revoked refresh token immediately rejects the session (`HTTP 401`) and flags potential token theft.
* **True Database Deletion**:
  * Physical `DELETE` cascade across `users`, `refresh_tokens`, and `scans` tables upon account deletion.
  * No soft-delete flags or residual data retained. Account deletion requires explicit two-step confirmation (including typing the account email).

---

### C. Rate Limiting & Denial-of-Service (DoS) Protection
* **Sliding-Window Limiter**: Implemented in [`app/security/rate_limiter.py`](app/security/rate_limiter.py).
* **Authentication Endpoints** (`/api/auth/register`, `/api/auth/login`, `/api/auth/refresh`):
  * Capped at **5 requests / minute per client IP** to mitigate brute-force credential stuffing and password guessing.
* **Scan & Analysis Endpoints** (`/api/scans`, `/api/analyze`):
  * Capped at **10 requests / minute per client IP / user** to protect server CPU resources from MediaPipe / OpenCV saturation and defend against LLM API cost abuse.
* **Standard Headers**: Throttled requests receive `HTTP 429 Too Many Requests` with a `Retry-After: <seconds>` response header.

---

### D. File Upload & Binary Integrity Hardening
* **Magic Byte Header Sniffing**: Implemented in [`app/security/validation.py`](app/security/validation.py).
  * Validates binary file signatures (`\xFF\xD8\xFF` for JPEG, `\x89PNG\r\n\x1a\n` for PNG, `RIFF...WEBP` for WebP) before handing data to image decoders.
  * Rejects extension spoofing (e.g. executable or shell script disguised as `.jpg`) with `HTTP 400 Bad Request`.
* **Payload Size Ceiling**: Enforces a strict **10 MB maximum upload size limit** (`HTTP 413 Content Too Large`) directly on the incoming byte stream before decoding.
* **Decompression Bomb Defense**: Verifies image dimensions ($\le 8192 \times 8192$ px, $\le 36\text{M}$ total pixels) to prevent memory exhaustion attacks.

---

### E. Secrets Management & CORS
* **Environment Variable Isolation**: Critical credentials (`JWT_SECRET_KEY`, `GEMINI_API_KEY`, `DATABASE_URL`) are read exclusively from environment variables.
* **Development Secret Warning**: In non-debug production environments, startup checks detect and log warnings if insecure default placeholder keys are present.
* **CORS Origin Lockdown**: Allowed origins (`ALLOWED_ORIGINS`) are locked to authorized frontend domains and local developer hosts; wildcard origins (`*`) are disallowed in production mode.
* **Error Response Sanitization**: Global exception handlers in production (`DEBUG=False`) suppress internal tracebacks, SQL statements, and file paths, returning safe generic error responses.

---

### F. Dependency Security & Continuous Auditing
* **Vulnerability Scanning**: Automated scanning of all direct and transitive dependencies via `pip-audit`.
* **Image Processing Defense**: Pinned versions of `opencv-python-headless` and `Pillow` to mitigate known binary buffer overflow vulnerabilities.

---

## 4. Security Verification & Test Suite

The security policies and mitigations are continuously verified via automated tests in [`tests/test_security.py`](tests/test_security.py):

```bash
# Run security test suite
pytest tests/test_security.py -v
```

Tested test vectors include:
1. `test_auth_rate_limiting`: Confirms 6th auth request in 60s is blocked with HTTP 429 and `Retry-After`.
2. `test_scan_rate_limiting`: Confirms 11th scan request in 60s is blocked with HTTP 429.
3. `test_reject_spoofed_text_file`: Confirms plain text disguised as `.jpg` is rejected with HTTP 400.
4. `test_reject_oversized_file`: Confirms payload $> 10\text{MB}$ is rejected with HTTP 413.
5. `test_db_backed_refresh_rotation_and_revocation`: Verifies refresh token rotation and rejection of replayed tokens.
