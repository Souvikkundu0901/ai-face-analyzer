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
| 🚀 **Current version** | `v0.4.0` — Persistence, Auth & Longitudinal Comparison |
| 🛠️ **Stack** | Python, FastAPI, MediaPipe, OpenCV, PostgreSQL / SQLAlchemy |
| ✅ **Status** | Active development — persistence & comparison complete, mobile client next |

---

## 📸 Sample Output

A live scan through the full pipeline — image quality gate, facial
geometry via 478 MediaPipe landmarks, classical OpenCV skin heuristics,
and the rules-gated LLM explanation layer.

Each recommendation card shows the deterministic rule ID that triggered
it (e.g. `REDNESS_MODERATE`) alongside the LLM's plain-language
explanation — generated only from that approved observation, never
invented independently.

> ⚕️ Sample scores shown are from a test image and are for
> demonstration purposes only — this analysis reflects visible
> characteristics, not a medical diagnosis.
<img width="1920" height="1080" alt="Screenshot 2026-08-24 235130" src="https://github.com/user-attachments/assets/556bfa12-b59a-4719-9e68-7c08c8dcc340" />
<img width="1920" height="1080" alt="Screenshot 2026-08-24 235140" src="https://github.com/user-attachments/assets/7d5b9a76-6862-4b20-abd9-2f3483859ca4" />

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
 
## ⚠️ Known Limitations
 
- 💡 Warm/incandescent lighting can skew redness detection (CIELAB `a*` channel); results are most consistent under neutral daylight. The comparison engine automatically warns if two scans were taken under disparate lighting.
- 🧔 Heavy facial hair or low bangs can compress geometry ratio estimates by obscuring chin/hairline landmarks.
- 🌓 Under-eye contrast detection is currently less reliable on very dark skin tones — calibration thresholds are configurable in `config.py`.
 
---
 
## 🗺️ Roadmap
 
- [x] 🧠 Core CV pipeline (geometry + skin heuristics)
- [x] 🧪 Automated test harness & calibration
- [x] 🧩 Recommendation rules engine + LLM explanation layer
- [x] 🗄️ Persistent scan history & longitudinal comparison
- [x] 🔐 Authentication & multi-user support (Zero-image retention)
- [ ] 📱 Flutter mobile client
- [ ] 🏭 Production hardening & bias evaluation across broader skin-tone and lighting datasets
 
---
 
## 📝 Changelog
 
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
