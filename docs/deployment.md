# AI Face Analyzer — Deployment, Operations & Reliability Guide

## 1. Overview
This document covers environment configuration, database schema management with Alembic migrations, environment parity, automated backup schedules, observability probes, and rollback procedures for the **AI Face Analyzer** service (v0.5.0).

---

## 2. Environment Variables Configuration

| Variable | Type | Required | Default / Example | Purpose |
| :--- | :---: | :---: | :--- | :--- |
| `DATABASE_URL` | String | **Yes** in Prod | `postgresql://user:pass@host:5432/dbname` (SQLite locally) | Connection string for PostgreSQL / SQLite persistence. Automatically converts legacy `postgres://` URLs to `postgresql://`. |
| `JWT_SECRET_KEY` | String | **Yes** in Prod | Random 64-char hex string | Secret key for signing and verifying HMAC-SHA256 JWT session and refresh tokens. |
| `GEMINI_API_KEY` | String | Optional | `AIzaSy...` | Google Gemini API key for dynamic explanation generation. If omitted, pipeline automatically falls back to deterministic rule explanations. |
| `GEMINI_MODEL` | String | Optional | `gemini-2.0-flash` | Gemini model variant. |
| `ALLOWED_ORIGINS` | String | Optional | `https://ai-face-analyzer.onrender.com,http://localhost:8000` | Comma-delimited list of allowed origins for CORS policy. |
| `DEBUG` | Boolean | Optional | `false` | Enables verbose stack traces in development mode. Must be `false` in production to prevent traceback leakage. |
| `SENTRY_DSN` | String | Optional | `https://...` | Sentry error tracking DSN. When unset, errors log locally without external dependencies. |
| `MAX_UPLOAD_SIZE_BYTES`| Integer | Optional | `10485760` (10 MB) | Strict maximum upload size limit enforced before decompression. |
| `RATE_LIMIT_AUTH_PER_MINUTE` | Integer | Optional | `5` | Request limit per IP on auth routes (`/api/auth/*`). |
| `RATE_LIMIT_SCAN_PER_MINUTE` | Integer | Optional | `10` | Request limit per client on analysis routes (`/api/scans`, `/api/analyze`). |

---

## 3. Database Schema Migrations (Alembic)

Database schema migrations are handled via **Alembic**.

### Running Migrations in Production:
On Render or Docker deployment, run migrations before starting the web server (e.g. in the build or pre-deploy command):

```bash
# Apply all pending migrations to the database
alembic upgrade head
```

### Creating New Migrations (Developers):
```bash
# Generate a new migration script from SQLAlchemy models
alembic revision --autogenerate -m "Add new column or table"

# Apply locally
alembic upgrade head

# Rollback one migration revision
alembic downgrade -1
```

---

## 4. Environment Parity: SQLite (Dev) vs PostgreSQL (Prod)

To ensure zero divergence between local SQLite development and production PostgreSQL:
1. **JSON Data Types**: All nested scan payload columns (`image_quality`, `face_metrics`, `skin_metrics`, `regions`, `report`) use `sa.JSON().with_variant(postgresql.JSONB, "postgresql")`.
   - On PostgreSQL: Leverages binary indexed `JSONB` for query speed and integrity.
   - On SQLite: Emulated via native JSON text column with automated serialization.
2. **Timezone Handling**: All `created_at` and `expires_at` timestamp columns use explicit `DateTime(timezone=True)` with UTC timestamps (`datetime.now(timezone.utc)`).
3. **Foreign Key Constraints & Cascading**: SQLite connections in testing use SQLite foreign key enforcement, matching PostgreSQL's `ON DELETE CASCADE` behavior on account deletion.

---

## 5. Health Probes & Monitoring

### Liveness and Readiness Probe:
* **Endpoint**: `GET /health` or `GET /api/health`
* **Response Payload**:
```json
{
  "status": "ok",
  "version": "analysis-v0.5.0",
  "timestamp": "2026-09-24T10:30:00.000000+00:00",
  "database": "connected",
  "detector": "ready",
  "model": {
    "path": "models/face_landmarker.task",
    "size": 3762464
  },
  "system": {
    "uptime_seconds": 3600,
    "total_requests": 142,
    "server_errors_5xx": 0
  },
  "pipeline_performance": {
    "sample_count": 24,
    "avg_detect_ms": 16.6,
    "avg_quality_gate_ms": 12.5,
    "avg_geometry_ms": 0.1,
    "avg_skin_ms": 86.7,
    "avg_rules_ms": 0.0,
    "avg_llm_ms": 22.2,
    "avg_total_ms": 115.9
  },
  "llm_performance": {
    "total_calls": 24,
    "successful_calls": 24,
    "fallback_triggers": 0,
    "success_rate_pct": 100.0,
    "fallback_rate_pct": 0.0,
    "avg_latency_ms": 22.2
  }
}
```

---

## 6. Backup Strategy

### Production PostgreSQL Backups (Render):
1. **Automated Daily Backups**: Render Managed PostgreSQL automatically performs daily logical backups retained according to the database tier.
2. **On-Demand Manual Snapshot**:
   ```bash
   # Create a manual PostgreSQL logical backup dump
   pg_dump "$DATABASE_URL" -Fc -f "ai_face_backup_$(date +%Y%m%d_%H%M%S).dump"
   ```
3. **Restoring from Backup**:
   ```bash
   # Restore dump to target database
   pg_restore --clean --if-exists -d "$DATABASE_URL" "ai_face_backup_<timestamp>.dump"
   ```

---

## 7. Rollback Procedures

If a faulty release is deployed to production:

1. **Rollback Web Application Deployment**:
   * In the Render Dashboard -> Select `ai-face-analyzer` web service -> Go to **Deploys** -> Locate the last known healthy deploy -> Click **Rollback to this deploy**.
2. **Rollback Database Migration** (if a breaking migration was applied):
   ```bash
   # Connect to Render Shell / CLI and step back the database revision
   alembic downgrade -1
   ```
3. **Verify Health**:
   * Inspect `GET /health` to verify `status: "ok"` and `database: "connected"`.
