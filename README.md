# AI Face Analyzer

A lightweight, high-performance computer vision service that analyzes facial geometry and visible skin characteristics from selfie photographs — built with **FastAPI**, **MediaPipe Face Landmarker (478 3D landmarks)**, and **classical OpenCV heuristics**.

Upload a selfie and get back facial proportion/symmetry metrics, a face-shape classification, skin analysis (redness, pigmentation, texture, spot detection), quality gating (sharpness/lighting/pose), a visual debug overlay, and an exportable PDF report — all through a single API and a bundled web UI.

![Python](https://img.shields.io/badge/python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688)
![MediaPipe](https://img.shields.io/badge/MediaPipe-0.10%2B-orange)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Features

- **478-point facial landmark detection** via MediaPipe's Face Landmarker task
- **Geometry analysis** — facial proportions, symmetry, and a margin-aware face-shape classifier
- **Skin analysis** — clean skin masking with OpenCV heuristics for redness, pigmentation, texture, and spot/blemish detection with confidence scoring
- **Quality gating** — independent sharpness, lighting, and pose sub-scores, with a rejection diagnostic overlay explaining failed checks
- **Visual debug overlay** — skin mask boundary, confidence-graded spot regions, and annotated face-shape ratios
- **Modern web UI** with summary score cards, skin meters, a proportional geometry table, overlay toggle, and one-click **PDF report export**
- **Automated invariant test harness** across lighting, blur, angle, multi-face, no-face, and skin-tone variations

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI, Pydantic |
| Computer Vision | MediaPipe Face Landmarker, OpenCV (headless) |
| Imaging | Pillow, NumPy |
| Frontend | Vanilla HTML/CSS/JS (`static/index.html`) |
| Deployment | Docker, Render, Vercel (serverless via `api/index.py`) |

---

## Directory Structure

```text
ai-face-analyzer/
├── app/
│   ├── main.py                 # FastAPI service with structured logging & timing
│   ├── schemas.py              # Pydantic response schemas
│   ├── config.py               # Centralized thresholds & constants
│   └── pipeline/
│       ├── face_detect.py      # MediaPipe Face Landmarker (478 3D landmarks)
│       ├── quality.py          # Image quality gate (sharpness/lighting/pose)
│       ├── geometry.py         # Proportions, symmetry & face-shape classifier
│       ├── skin.py             # Clean skin mask + OpenCV heuristics
│       ├── regions.py          # Normalized region representations
│       └── overlay.py          # Visual debug overlay & rejection diagnostics
├── api/
│   └── index.py                # Vercel serverless entrypoint
├── models/                     # face_landmarker.task model
├── static/
│   └── index.html              # Web UI with PDF report export
├── tests/
│   ├── sample_images/          # Categorized test fixtures
│   └── test_pipeline.py        # Automated invariant test harness
├── Dockerfile
├── Procfile                    # Render/Heroku start command
├── render.yaml                 # Render deployment config
├── vercel.json                 # Vercel routing config
└── requirements.txt
```

---

## Getting Started

### Prerequisites
- Python 3.11+
- pip

### 1. Clone & install dependencies

```bash
git clone https://github.com/Souvikkundu0901/ai-face-analyzer.git
cd ai-face-analyzer
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Run the server

```bash
uvicorn app.main:app --reload --port 8000
```

### 3. Open the app

Visit **http://localhost:8000** — upload or capture a selfie, review the geometry/skin metrics, toggle the debug overlay, and export a PDF report.

---

## Running with Docker

```bash
docker build -t ai-face-analyzer .
docker run -p 8000:8000 ai-face-analyzer
```

## Deployment

- **Render**: deploys directly from `render.yaml`
- **Vercel**: serverless deployment via `api/index.py` and `vercel.json`
- **Docker/Heroku**: use the included `Dockerfile` / `Procfile`

---

## Running Tests

```bash
python -m unittest tests/test_pipeline.py
```

Expected output:

```text
...........
----------------------------------------------------------------------
Ran 11 tests in 2.557s

OK
```

### Adding a new test image

Place a JPEG/PNG in the relevant subfolder under `tests/sample_images/`, then re-run the suite to confirm the pipeline processes or rejects it as expected:

| Folder | Use for |
|---|---|
| `good_lighting/` | Good quality selfies |
| `low_light/` | Dark/underexposed photos |
| `blurry/` | Motion or out-of-focus blur |
| `no_face/` | Non-portrait / blank images |
| `multiple_faces/` | Group photos |
| `extreme_angle/` | Sideways or extreme tilt |
| `varied_skin_tones/` | Different skin tones |

---

## Known Limitations

1. **Ambient lighting color cast** — warm incandescent/yellow indoor light artificially elevates the CIELAB `a*` channel; neutral/daylight lighting gives the most consistent baseline.
2. **Heavy facial hair / bangs** — thick beards or low bangs can obscure chin/hairline landmarks, slightly compressing face-ratio estimates.
3. **Very dark skin tones** — under-eye luminance contrast is subtler on darker complexions; thresholds in `app/config.py` can be tuned per regional lighting calibration.

---

## Disclaimer

This project is for **educational and experimental purposes only**. It is not a medical or dermatological diagnostic tool, and its output should not be used for health, cosmetic, or clinical decision-making.

---

## License

Released under the [MIT License](LICENSE).
