# 🧠 AI Face Analyzer

A computer vision service that analyzes facial geometry and visible skin
characteristics from a selfie — built with **FastAPI**, **MediaPipe Face
Mesh** (478 landmarks), classical **OpenCV** heuristics, and a
rules-gated **LLM explanation layer**.

The system produces measurable metrics, confidence scores, visual
overlays, and plain-language observations. It reports what is visibly
present in an image — it does **not** diagnose medical conditions.

---

## 📌 Overview

| | |
|---|---|
| 🚀 **Current version** | `v0.5.0` — Production Hardening, Observability & Bias Evaluation |
| 🛠️ **Stack** | Python, FastAPI, MediaPipe, OpenCV, PostgreSQL / SQLAlchemy, Alembic |
| ✅ **Status** | Production ready — hardened security, full observability, calibrated fairness |

---

## ✨ What's New in v0.5.0
 
Building on the persistence and comparison capabilities from v0.4.0, this release hardens the service for production reliability, security, observability, and empirical skin-tone fairness:

- 🔒 **Rate Limiting Engine** — In-memory sliding-window throttling per IP / authenticated client. Auth endpoints (`/api/auth/*`) are throttled at **5 req/min** (mitigating brute force), while compute/LLM-heavy scan endpoints (`/api/scans`, `/api/analyze`) are throttled at **10 req/min** with standard `HTTP 429` and `Retry-After` headers.
- 🛡️ **Multi-Layer Upload Validation & Magic Byte Sniffing** — Replaced extension/MIME header trust with true binary magic byte inspection (`\xFF\xD8\xFF` JPEG, `\x89PNG\r\n\x1a\n` PNG, `RIFF...WEBP` WebP). Enforces strict 10MB payload bounds and decompression bomb protections.
- 🌐 **CORS & Secrets Hardening** — Locked CORS origins to configured production and development domains (`ALLOWED_ORIGINS`). Ensured all credentials (`JWT_SECRET_KEY`, `GEMINI_API_KEY`, `DATABASE_URL`) are strictly loaded from environment variables with sanitized production error responses.
- ⏱️ **Structured Request Tracing & Per-Stage Pipeline Profiling** — Every request is injected with a unique `X-Request-ID`. Analysis executions record microsecond-accurate timing across all 6 pipeline stages (`detect_ms`, `quality_gate_ms`, `geometry_ms`, `skin_ms`, `rules_ms`, `llm_ms`, `total_ms`).
- 📊 **LLM Observability & Error Tracking** — Aggregates LLM call success rates, fallback-template triggers, and average latency. Integrated `sentry-sdk` support for cloud exception monitoring with zero-PII guards.
- 🩺 **Comprehensive Health & Readiness Probes** — Upgraded `GET /health` with live PostgreSQL/SQLite database probes, MediaPipe model validation, uptime tracking, and rolling performance averages.
- ⚖️ **Empirical Bias Evaluation & Fairness Calibration** — Built an automated 24-sample evaluation dataset across Fitzpatrick tones (I–VI), lighting casts, and face shapes. Calibrated pigmentation variance using luminance-relative normalization ($CV_{L^*}$), eliminating false positive skew on fair skin while maintaining sensitivity across deep complexions.
- 🗃️ **Alembic Database Migrations & Operations Guide** — Added declarative Alembic migration tooling (`alembic upgrade head`), cross-dialect JSONB/JSON parity, and documented backup/rollback workflows in [`docs/deployment.md`](docs/deployment.md).
- 🧪 **Zero Vulnerabilities & 69 Tests Passing** — Clean `pip-audit` dependency audit and 100% test pass rate across unit, auth, security, and monitoring suites.

---

## ✨ What's New in v0.4.0
 
Building on the calibrated pipeline and rules/LLM explanation layers, this release
adds full user persistence, privacy-first storage, and longitudinal scan comparisons.
 
- 🔐 **Authentication & Session Security** — Email/password signup and login with direct
  `bcrypt` password hashing, short-lived JWT access tokens, and DB-backed refresh token
  rotation with automatic reuse detection and immediate revocation.
- 🗄️ **PostgreSQL Data Model with JSONB** — Efficient relational user schema with flexible
  `JSONB` columns for structured CV metrics and recommendations. Compatible with SQLite
  for effortless zero-config local testing.
- 🛡️ **Strict Zero-Image Retention Privacy** — Original selfies are processed entirely
  in-memory and immediately discarded. Only anonymized, derived numerical metrics are
  ever saved to the database.
- 🗑️ **True Database Deletion** — Real physical `DELETE` cascade across scans, tokens, and
  user records. Zero soft-delete flags or retained personal data. Account deletion requires
  a safe two-step confirmation flow including typing the account email.
- 📈 **Longitudinal Scan Comparison & Delta Engine** — Track changes over time across redness,
  pigmentation, texture, spots, and symmetry. Includes structural face-shape stability checks.
- ⚠️ **Capture-Condition Comparability Warnings** — Flags scans where lighting, quality, or
  pose disparities ($\ge 0.20$ quality gap, $\ge 0.25$ lighting/pose disparity) make direct
  metric comparison unreliable.
- 🖥️ **Upgraded Web Interface** — Dedicated Scanner vs. History views, side-by-side comparison
  dialog with metric delta badges and warning banners, auth modals, and account privacy controls.
 
---
 
## ✨ What's New in v0.3.0

Building on the hardened, calibrated pipeline from v0.2.0, this release
adds the layer that turns raw scores into readable, safe explanations.

- 🧩 **Deterministic recommendation rules engine** — a pure, unit-tested
  module that maps calibrated CV scores to a fixed catalog of
  recommendation IDs. No ML, no LLM, no ambiguity: same input always
  produces the same output.
- 💬 **LLM explanation layer** — takes only the recommendation IDs
  already decided by the rules engine and turns them into calm,
  factual, non-alarming prose. The LLM never sees raw scores
  unsupervised and never invents a new observation.
- 🛡️ **Schema-validated LLM output** with automatic fallback to canned
  template text if the API call fails, times out, or returns malformed
  output — the report is never dependent on a third-party call
  succeeding.
- 🚫 **Medical-language safety net** — a keyword filter runs on
  generated text as a backstop to the prompt-level constraints.
- ⚡ **Response caching** by recommendation-ID combination to avoid
  redundant LLM calls across scans that trigger the same rule set.
- 📄 **Extended report section** in the API response with per-
  observation explanations, a summary, and a standing disclaimer.

See [Changelog](#-changelog) for the full version history.

---

## ⚙️ How It Works

```text
📸 Selfie
   ↓
🔍 Image Quality Gate        (reject blurry / dark / no-face / multi-face input)
   ↓
🧑‍💻 Face Detection & Landmarks (MediaPipe, 478 points)
   ↓
📐 Geometry & Shape Analysis  (relative ratios, symmetry, shape heuristic)
   ↓
🩹 Skin Analysis              (redness, pigmentation, texture, spots, under-eye — skin-masked)
   ↓
📊 Structured Metrics JSON
   ↓
🧩 Recommendation Rules Engine (deterministic — decides WHAT to report)
   ↓
💬 LLM Explanation Layer       (explains what was already decided — never invents)
   ↓
📄 Final Report
```

**Core design rule:** CV models detect. The rules engine decides what's
reportable. The LLM only explains. This separation is intentional and
should not be bypassed — see [Design Principles](#-design-principles).

---

## 🌟 Features

- 📐 **Face geometry** — proportional ratios, symmetry score, heuristic
  face shape classification with confidence.
- 🩹 **Skin analysis** — redness, pigmentation variation, texture,
  spot-like region detection, under-eye darkness — all computed on a
  landmark-derived skin mask that excludes eyes, brows, lips, and
  nostrils.
- 🚦 **Quality gate** that rejects unreliable input (blur, poor
  lighting, extreme angle, no face, multiple faces) with a specific
  reason.
- 🖼️ **Visual debug overlay** — skin mask boundary, flagged regions
  with a confidence gradient, and shape classification labels.
- 🧩 **Deterministic recommendation engine** with a fixed, auditable
  recommendation catalog.
- 💬 **LLM-generated explanations** — non-medical, non-alarming, with
  automatic fallback and a safety-net content filter.
- 🧪 **Automated test harness** with relative-ordering invariants (e.g.
  a visibly redder test image must score higher than a fairer one).
- 🖥️ **Web UI** with score cards, skin meters, a geometry table, an
  overlay toggle, and a printable/exportable PDF report.

---

## 🧭 Design Principles
 
1. 🔬 CV models detect; they do not diagnose.
2. 🧩 The rules engine decides what recommendations are allowed — never
   the LLM.
3. 💬 The LLM explains approved results; it never invents observations.
4. 📏 Facial measurements are relative/normalized — no exact real-world
   dimensions are claimed without calibrated depth.
5. 🚫 Poor-quality selfies are rejected rather than analyzed unreliably.
6. 🔒 **Privacy by Default**: Zero image retention. Selfies are processed in-memory
   and immediately discarded; only derived numeric metrics are stored.
7. 🗑️ **True Data Ownership**: Account and scan deletions are physical, permanent
   database deletions cascading immediately without soft-delete tombstones.
8. 🏷️ Every response carries a `pipeline_version` for reproducibility.
9. ⚕️ No medical or diagnostic language appears anywhere in the output.
 
---
 
## 📁 Project Structure
 
```text
ai-face-analyzer/
├── app/
│   ├── main.py                  # FastAPI service, auth & scan endpoints
│   ├── schemas.py                # Pydantic auth, scan, delta & comparison models
│   ├── config.py                 # Centralized thresholds, DB & JWT settings
│   ├── auth/
│   │   ├── security.py           # Bcrypt hashing, JWT issuance & jti token revocation
│   │   └── dependencies.py       # FastAPI get_current_user security dependency
│   ├── db/
│   │   ├── session.py            # SQLAlchemy engine, session factory & init_db
│   │   └── models.py             # User, RefreshToken & Scan ORM models (JSONB)
│   ├── comparison/
│   │   └── service.py            # Longitudinal deltas & comparability warning engine
│   ├── pipeline/
│   │   ├── quality.py            # Image quality gate
│   │   ├── face_detect.py        # MediaPipe Face Landmarker
│   │   ├── geometry.py           # Ratios, symmetry, shape classifier
│   │   ├── skin.py               # Skin mask + redness/pigmentation/texture/spots
│   │   ├── regions.py            # Normalized region output
│   │   └── overlay.py            # Debug overlay & rejection diagnostics
│   ├── rules/
│   │   ├── engine.py             # Deterministic recommendation engine
│   │   ├── recommendations.py    # Fixed recommendation catalog
│   │   └── thresholds.py         # Score bands that trigger each recommendation
│   └── llm/
│       ├── client.py             # LLM API wrapper
│       ├── prompt.py             # Prompt construction
│       └── schema.py             # Validated LLM output shape
├── models/                       # MediaPipe face_landmarker.task
├── tests/
│   ├── sample_images/            # Categorized test fixtures
│   ├── expected/notes.md         # Qualitative expectations & invariants
│   ├── test_pipeline.py          # CV pipeline & quality gate test suite
│   ├── test_rules_engine.py      # Deterministic recommendation rules test suite
│   ├── test_llm_integration.py   # LLM schema, fallback & safety tests
│   ├── test_auth.py              # Auth, JWT, refresh rotation & revocation tests
│   ├── test_scans.py             # Multi-tenant isolation & cascade deletion tests
│   └── test_comparison.py        # Longitudinal comparison & warning tests
├── static/
│   └── index.html                # Web UI + history, comparison & privacy controls
├── public/                       # Vercel / static hosting sync
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites

- 🐍 Python 3.11+
- 🔑 An LLM API key (set in `.env`, see `.env.example`)

### Install

```bash
git clone https://github.com/Souvikkundu0901/ai-face-analyzer.git
cd ai-face-analyzer
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env          # then add your LLM API key
```

### Run

```bash
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000` 🌐 to use the web UI, or call the API
directly:

```bash
curl -X POST http://localhost:8000/api/analyze \
  -F "image=@path/to/selfie.jpg"
```

### Run Tests
 
```bash
pytest -v
```
 
---
 
## 🔌 API Reference
 
### 🔐 Auth Endpoints
 
- `POST /api/auth/register` — Register a new account (`email`, `password`). Returns JWT access & refresh tokens.
- `POST /api/auth/login` — Authenticate existing user. Returns JWT access & refresh tokens.
- `POST /api/auth/refresh` — Rotate refresh token. DB-backed with automatic reuse detection & immediate revocation.
- `GET /api/auth/me` — Return the current authenticated user's profile.
- `DELETE /api/users/me` — **Real cascading deletion** of account, scans, and active tokens.
 
### 📸 Scan & Analysis Endpoints
 
- `POST /api/analyze` — Anonymous scan fallback. Accepts a selfie (`multipart/form-data`, field `image`). Returns full metrics JSON and recommendations without persisting.
- `POST /api/scans` — Authenticated scan persistence. Executes pipeline, stores derived metrics in PostgreSQL/SQLite `JSONB`, and discards the image immediately.
- `GET /api/scans` — Paginated list of the user's past scans (`?page=1&limit=20`), sorted newest-first.
- `GET /api/scans/{scan_id}` — Detailed report for a specific persisted scan owned by the user.
- `DELETE /api/scans/{scan_id}` — **Real physical deletion** of a specific scan record from the database.
 
### 📈 Longitudinal Comparison
 
- `GET /api/scans/compare?ids=<id1>,<id2>` — Chronological delta analysis between two scans. Returns metric percentage deltas, face shape stability verification, and automatic **capture condition comparability warnings** (triggered if quality gap $\ge 0.20$ or lighting/pose disparity $\ge 0.25$).
 
### 🖼️ Diagnostic & Utility
 
- `GET /api/analyze/{scan_id}/overlay` — Annotated debug image displaying landmarks, skin mask boundary, and flagged regions.
- `GET /health` — Liveness check. ❤️
 
Full Pydantic schemas are defined in [`app/schemas.py`](app/schemas.py).
 
---
 
## ⚠️ Known Limitations & Empirical Findings (v0.5.0 Evaluation)
 
- 💡 **Illuminant Color Constancy Sensitivity** — Analysis assumes balanced natural daylight (5000K–5500K). Warm incandescent (2700K) bulbs inflate CIELAB $a^*$ redness scores (up to $0.99$, mimicking erythema), while cool fluorescent (6500K) lighting suppresses redness ($0.00$). The longitudinal comparison engine automatically detects and warns if two scans were captured under disparate lighting conditions.
- 📐 **2D Face Shape Discretization** — In single 2D frontal selfies without 3D jaw angle depth sensors, morphology estimates cluster into broad 2D aspect ratio archetypes (primarily `round` for face ratios $< 1.35$ and `rectangle` for $> 1.40$).
- 🧔 **Facial Hair & Hairlines** — Heavy beards, thick stubble, or low bangs obscure chin and forehead landmark contours, compressing estimated vertical face and jaw ratios.
- 🌓 **Periorbital Contrast Sensitivity** — Under-eye shade detection evaluates local luminance deficits relative to adjacent cheek zones; extreme top-down directional lighting or heavy brow bone shadows can elevate under-eye contrast scores.
- 🎨 **Skin Tone Pigmentation Calibration** — Evaluated across the 6-tier Fitzpatrick scale (I–VI). In v0.5.0, pigmentation variance uses luminance-relative coefficient of variation ($CV_{L^*}$), maintaining equity across light and deep complexions ($0.12\text{--}0.25$ baseline range). However, severe low-light underexposure ($L^* < 30$) can dampen high-frequency gradient edge detection.
 
---
 
## 🗺️ Roadmap
 
- [x] 🧠 Core CV pipeline (geometry + skin heuristics)
- [x] 🧪 Automated test harness & calibration
- [x] 🧩 Recommendation rules engine + LLM explanation layer
- [x] 🗄️ Persistent scan history & longitudinal comparison
- [x] 🔐 Authentication & multi-user support (Zero-image retention)
- [x] 🏭 Production hardening, rate limiting, observability & empirical bias evaluation (v0.5.0)
- [ ] 📱 Flutter mobile client
- [ ] 🌐 Client-side automatic Gray World white-balance pre-processing
 
---
 
## 📝 Changelog
 
### v0.5.0
- 🔒 Added sliding-window rate limiting on Auth (5 req/min) and Scan (10 req/min) endpoints with standard `HTTP 429` retry headers.
- 🛡️ Hardened file upload validation with binary magic byte sniffing (JPEG, PNG, WebP) and strict 10MB limits.
- 🌐 Locked CORS configuration to explicitly allowed origins and sanitized production exception tracebacks.
- ⏱️ Added structured request tracing (`X-Request-ID`) and per-stage pipeline timing telemetry (`detect`, `gate`, `geo`, `skin`, `rules`, `llm`).
- 📊 Wired LLM observability metrics (success count, fallback rate, latency tracking) and optional Sentry error tracking integration.
- 🩺 Upgraded `/health` probe with live PostgreSQL/SQLite DB connectivity checks and system telemetry.
- ⚖️ Built a 24-sample synthetic evaluation set across Fitzpatrick I–VI tones; calibrated pigmentation metric for skin tone fairness.
- 🗃️ Added Alembic database migration tooling (`alembic upgrade head`) and created `docs/deployment.md`.
- 🧪 Expanded automated test suite to 69 tests across security, monitoring, auth, pipeline, and rules.
 
### v0.4.0
- 🔐 Added user authentication with bcrypt, JWT access tokens, and DB-backed refresh token rotation with immediate reuse revocation.
- 🗄️ Added PostgreSQL schema with native `JSONB` support for metrics and cross-compatible SQLite support for development.
- 🛡️ Implemented strict zero-image retention privacy: photos are analyzed in-memory and immediately destroyed.
- 🗑️ Added real physical database deletion for both individual scans and entire user accounts with cascading cleanup.
- 📈 Added longitudinal comparison engine with metric deltas, face-shape stability check, and capture condition comparability warnings.
- 🖥️ Redesigned web UI with Scanner / History views, compare modal, delta badges, and account privacy controls.
- 🧪 Added full test coverage for auth, authorization isolation, cascades, and comparison logic (58 tests total).
 
### v0.3.0
- 🧩 Added deterministic recommendation rules engine.
- 💬 Added LLM explanation layer with schema validation and fallback.
- 🚫 Added medical-language safety-net filter.
- ⚡ Added recommendation-based response caching.

### v0.2.0
- 🧪 Automated test harness with relative-ordering invariants.
- ⚙️ Centralized all thresholds/config into `app/config.py`.
- 🖼️ Upgraded debug overlay (skin mask boundary, confidence gradient,
  rejection diagnostics).
- 🎯 Realistic, non-flat confidence scoring for shape and region
  detection.
- 🛡️ Robustness improvements (downscaling, angle tolerance, structured
  logging).
- 🎨 Redesigned web UI with printable PDF report export.

### v0.1.0
- 🌱 Initial pipeline: image quality gate, MediaPipe face detection and
  landmarks, geometry ratios, face-shape heuristic, skin heuristics
  (redness, pigmentation, texture, spots, under-eye darkness).

---

## ⚕️ Disclaimer

This project reports visible facial and skin characteristics only. It
is not a medical device, does not perform diagnosis, and should not be
used as a substitute for consulting a dermatologist or other qualified
professional.

---

<div align="center">

**🧑‍💻 Directed & Created by [Souvik Kundu](https://github.com/Souvikkundu0901)**

[GitHub](https://github.com/Souvikkundu0901) · [LinkedIn](https://linkedin.com/in/souvikkundu19)

</div>
