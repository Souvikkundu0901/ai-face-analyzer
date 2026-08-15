# AI Face Analyzer (Phase 2 / Hardening + Visualization)

A lightweight, high-performance computer vision pipeline service built with **FastAPI**, **MediaPipe Face Mesh (478 landmarks)**, and **classical OpenCV heuristics** for analyzing facial geometry and visible skin characteristics from selfie photographs.

---

## What's New in Phase 2 (`analysis-v0.2.0`)

1. **Automated Test Harness & Invariant Testing**:
   - Subfolder test runner across `good_lighting/`, `low_light/`, `blurry/`, `multiple_faces/`, `no_face/`, `extreme_angle/`, `varied_skin_tones/`.
   - Relative ordering invariant assertions (`redness(flushed) > redness(fair)`, `texture(textured) > texture(fair)`).
   - Expected qualitative behavior recorded in [`tests/expected/notes.md`](file:///C:/Users/Souvik/OneDrive/Desktop/AI%20face/tests/expected/notes.md).

2. **Centralized Configuration & Calibration**:
   - All magic numbers, thresholds, and weighting factors centralized in [`app/config.py`](file:///C:/Users/Souvik/OneDrive/Desktop/AI%20face/app/config.py) with full explanatory comments.

3. **Upgraded Visual Debug Overlay**:
   - Renders exact clean skin mask boundary.
   - Renders detected spot regions sized by radius and colored with a continuous confidence gradient (green → yellow → red).
   - Annotates face shape classification with underlying proportional ratios.
   - Includes **Rejection Diagnostic Overlay** explaining why an image failed quality checks.

4. **Realistic Confidence Scoring**:
   - Multi-archetype distance metric with decision boundary margin penalties for face shape.
   - Peak signal-to-noise ratio (SNR) confidence scoring for detected spot regions.
   - Independent quality gate sub-scores (sharpness, lighting, pose).

5. **Robustness & Edge Cases**:
   - Large image downscaling (`> 2048px`) to protect inference speed while maintaining normalized coordinates.
   - Gentle degradation for minor head angles.
   - Structured logging with execution time telemetry and `DEBUG` flag support.

6. **Redesigned Modern UI & Printable PDF Report**:
   - Pink & neutral aesthetic (`#FF659D`, `#FFE6F0`, `#1E293B`).
   - Summary score cards, skin meters, proportional geometry table, overlay toggle, and **Export PDF Report** export.

---

## Directory Structure

```text
ai-face-analyzer/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI service with structured logging & timing
│   ├── schemas.py               # Pydantic schemas (Section 5 & 6)
│   ├── config.py                # Centralized thresholds & constants
│   └── pipeline/
│       ├── __init__.py
│       ├── face_detect.py       # MediaPipe Face Landmarker (478 3D landmarks)
│       ├── quality.py           # Image quality gate
│       ├── geometry.py          # Proportions, symmetry & margin-aware shape classifier
│       ├── skin.py              # Clean skin mask + OpenCV heuristics (redness, pigmentation, texture, spots)
│       ├── regions.py           # Normalized region representations
│       └── overlay.py           # Visual debug overlay & rejection diagnostic renderer
├── models/                      # Auto-downloaded face_landmarker.task model
├── tests/
│   ├── sample_images/           # Categorized test fixtures
│   │   ├── good_lighting/
│   │   ├── low_light/
│   │   ├── blurry/
│   │   ├── multiple_faces/
│   │   ├── no_face/
│   │   ├── extreme_angle/
│   │   └── varied_skin_tones/
│   ├── expected/
│   │   └── notes.md             # Qualitative expectations & invariants
│   └── test_pipeline.py         # Automated test harness
├── static/
│   └── index.html               # Redesigned UI client with PDF Report export
├── requirements.txt
├── .env.example
└── README.md
```

---

## Setup & Running

### 1. Activate Virtual Environment & Install Dependencies

```powershell
# Windows
cd "C:\Users\Souvik\OneDrive\Desktop\AI face"
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Start the Server

```powershell
uvicorn app.main:app --reload --port 8000
```

### 3. Open the UI & Generate Reports
Visit **`http://localhost:8000`** in your browser:
- Upload or snap a selfie.
- View facial geometry metrics, symmetry, and skin meters.
- Click **Export PDF Report** to generate/print a clean clinical analysis sheet.

---

## Running the Automated Test Harness

Run all subfolder and invariant tests:

```powershell
python -m unittest tests/test_pipeline.py
```

### What a Passing Run Looks Like:

```text
...........
----------------------------------------------------------------------
Ran 11 tests in 2.557s

OK
```

### How to Add a New Test Image:
1. Place your JPEG/PNG photo in the appropriate subfolder inside `tests/sample_images/`:
   - Good quality selfies -> `good_lighting/`
   - Dark/underexposed photos -> `low_light/`
   - Motion or out-of-focus blur -> `blurry/`
   - Non-portrait / blank images -> `no_face/`
   - Group photos -> `multiple_faces/`
   - Sideways or extreme tilt -> `extreme_angle/`
   - Different skin tones -> `varied_skin_tones/`
2. Run `python -m unittest tests/test_pipeline.py` to ensure the pipeline processes or rejects it as expected.

---

## Known Limitations & Calibration Insights

1. **Ambient Lighting Color Cast**: Warm incandescent or yellow indoor bulbs artificially elevate CIELAB `a*` channel values. Testing with neutral/daylight illumination provides the most consistent baseline.
2. **Heavy Facial Hair / Bangs**: Thick beards or low forehead bangs obscure outer chin and hairline landmark points, which can slightly compress face ratio estimates.
3. **Very Dark Skin Tones**: Under-eye luminance contrast is subtler on darker complexions; calibration thresholds in `config.py` can be customized based on regional lighting calibration.
