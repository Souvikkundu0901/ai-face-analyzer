# AI Face Analyzer — Build Spec (Phase 1 / MVP)

> Handoff doc for an AI coding agent. Goal: get a working end-to-end CV
> pipeline running fast, with minimal moving parts. No Flutter, no
> microservices, no LLM in this phase. Prove the core analysis works first.

---

## 1. What We're Building (Phase 1 Only)

A single FastAPI service that:

1. Accepts a selfie image (upload).
2. Runs an image-quality gate (reject bad input).
3. Detects the face and extracts landmarks (MediaPipe Face Mesh).
4. Computes face geometry ratios + heuristic face-shape classification.
5. Computes skin heuristics using classical OpenCV (no trained model):
   redness, pigmentation variation, texture, under-eye darkness,
   spot-like region count.
6. Returns one structured JSON response matching the schema in Section 5.
7. Optionally renders a debug overlay image (landmarks + flagged regions)
   for visual sanity-checking.

**Explicitly out of scope for Phase 1:** Flutter app, Spring Boot backend,
auth, database, object storage, LLM explanation layer, recommendation
rules engine, scan history/progress tracking, PyTorch/ONNX models. Add
these in later phases only after the core pipeline is validated.

---

## 2. Tech Stack (Phase 1)

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | |
| API | FastAPI + Uvicorn | fast to stand up, auto docs |
| Face detection/landmarks | MediaPipe (Tasks API, Face Landmarker) | already familiar, no training needed, 478 landmarks |
| Computer vision | OpenCV | HSV/LAB color analysis, blob detection, texture |
| Numeric | NumPy | |
| Validation | Pydantic | request/response schemas |
| Image I/O | Pillow | |
| Client for testing | curl / Postman / a single static HTML page with a file input | no need for Flutter yet |

No PyTorch, no ONNX, no database, no cloud storage in this phase.

---

## 3. Project Structure

```text
ai-face-analyzer/
├── app/
│   ├── main.py                 # FastAPI app + routes
│   ├── schemas.py               # Pydantic request/response models
│   ├── pipeline/
│   │   ├── quality.py           # image quality gate
│   │   ├── face_detect.py       # MediaPipe face detection + landmarks
│   │   ├── geometry.py          # ratios + face-shape heuristic
│   │   ├── skin.py              # redness / pigmentation / texture / spots
│   │   ├── regions.py           # normalized region coordinates for overlay
│   │   └── overlay.py           # debug visualization renderer
│   └── config.py                # thresholds, constants
├── models/                      # downloaded MediaPipe model files (.task)
├── tests/
│   ├── sample_images/           # a handful of test selfies, varied lighting/skin tone
│   └── test_pipeline.py
├── static/
│   └── index.html               # minimal upload form for manual testing
├── requirements.txt
├── .env.example
└── README.md
```

---

## 4. API Contract

### `POST /api/analyze`

**Request:** multipart/form-data, field `image` (jpeg/png).

**Response:** `200 OK` with JSON matching Section 5, or `422` with a
quality-gate rejection reason (see Section 6).

### `GET /api/analyze/{scan_id}/overlay` (optional, Phase 1 stretch)

Returns a PNG with landmarks and flagged regions drawn on the original
image, for visual debugging. No persistence required — regenerate on
demand from an in-memory cache or just re-run analysis.

### `GET /health`

Basic liveness check.

---

## 5. Response Schema

```json
{
  "scan_id": "uuid",
  "pipeline_version": "analysis-v0.1.0",
  "image_quality": {
    "score": 0.0,
    "lighting": 0.0,
    "sharpness": 0.0,
    "pose": 0.0,
    "passed": true
  },
  "face": {
    "shape": "oval",
    "shape_confidence": 0.0,
    "symmetry_score": 0.0,
    "face_ratio": 0.0,
    "ratios": {
      "jaw_width_to_face_width": 0.0,
      "forehead_width_to_face_width": 0.0,
      "eye_distance_to_face_width": 0.0,
      "nose_width_to_face_width": 0.0,
      "lip_width_to_face_width": 0.0
    }
  },
  "skin": {
    "visible_spots": 0,
    "redness_score": 0.0,
    "pigmentation_score": 0.0,
    "texture_score": 0.0,
    "under_eye_score": 0.0
  },
  "regions": [
    { "type": "spot_like_region", "x": 0.0, "y": 0.0, "radius": 0.0, "confidence": 0.0 }
  ],
  "warnings": []
}
```

All scores normalized 0.0–1.0. `warnings` holds soft issues (e.g. "mild
uneven lighting") that didn't fail the quality gate but may reduce
reliability.

---

## 6. Image Quality Gate — Rules

Reject (`422`) before running any analysis if:

- No face detected, or more than one face detected.
- Face bounding box < ~20% of frame (too far / too small).
- Blur score below threshold (Laplacian variance).
- Extreme over/under-exposure (mean brightness histogram check).
- Face yaw/pitch/roll beyond threshold (use landmark geometry, not a
  separate pose model).

Return a specific reason string per failure so the caller can show
useful retake guidance, e.g.:

```json
{ "passed": false, "reason": "blur", "message": "Image is too blurry. Hold the camera steady and retake in good light." }
```

---

## 7. Skin Heuristics — Implementation Notes (classical CV, no training)

- **Redness:** convert to LAB or HSV, isolate the `a*` channel (LAB) or
  hue band around red, mask to skin region only (exclude eyes/lips/hair
  via landmark-derived mask), compute normalized mean/variance in
  cheek + forehead regions.
- **Pigmentation variation:** grayscale std-dev within skin mask, or
  local contrast via a sliding window; flag high-variance patches.
- **Texture:** Local Binary Patterns (LBP) or GLCM contrast on skin
  mask; higher score = rougher/more textured.
- **Under-eye darkness:** compare mean luminance of under-eye landmark
  region vs. adjacent cheek region.
- **Spot-like regions:** blob detection (`cv2.SimpleBlobDetector` or
  DoG) within skin mask on the redness/pigmentation channel; filter by
  size/circularity; output normalized (x, y) + confidence per blob.

Use MediaPipe's 478 landmarks to build the skin mask (exclude eyes,
eyebrows, lips, nostrils) so scores aren't polluted by non-skin pixels.

---

## 8. Face Geometry & Shape Heuristic

Use landmark indices for face width, jaw width, forehead width, face
height (chin to hairline approximation via forehead landmarks),
inter-eye distance, nose width, lip width. Compute ratios (Section 5).
Classify shape with simple rule-based thresholds on those ratios
(oval/round/square/rectangle/heart/diamond) — this does **not** need a
trained classifier for V1. Attach a confidence score based on how
cleanly the ratios fall into a bucket (e.g. distance from threshold
boundary, normalized).

---

## 9. Non-Negotiable Rules (carried over from system design doc)

1. CV detects; it does not diagnose. No medical language anywhere in
   output (no "rosacea", "eczema", "cancer", etc.) — use "redness
   detected", "pigmentation variation detected", "spot-like region
   detected".
2. Use relative/normalized measurements only — never claim exact
   real-world cm/mm without calibrated depth.
3. Reject poor-quality input rather than returning unreliable scores.
4. Every response includes `pipeline_version` for reproducibility.
5. Validate against a small varied test set (different lighting, skin
   tones, angles) before considering Phase 1 "done" — don't just test
   on one well-lit photo of yourself.

---

## 10. Environment Setup

```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install fastapi uvicorn[standard] mediapipe opencv-python-headless numpy pydantic pillow python-multipart
```

Download the MediaPipe Face Landmarker task file into `models/`:
`face_landmarker.task` from Google's MediaPipe model zoo.

Run:

```bash
uvicorn app.main:app --reload --port 8000
```

Test manually via `static/index.html` (simple `<input type="file">` +
fetch to `/api/analyze`) or via curl:

```bash
curl -X POST http://localhost:8000/api/analyze -F "image=@tests/sample_images/sample1.jpg"
```

---

## 11. Definition of Done for Phase 1

- [ ] `/api/analyze` returns valid JSON matching Section 5 schema for a
      good-quality test image.
- [ ] Quality gate correctly rejects at least: blurry image, no face,
      multiple faces, extreme darkness.
- [ ] Face shape + ratios look sane across 5+ varied test photos
      (manually eyeball reasonableness — no formal accuracy claim needed
      yet).
- [ ] Skin heuristic scores visibly respond to obvious differences
      between test images (e.g. a redder face scores higher redness).
- [ ] Debug overlay (if implemented) draws landmarks + flagged spot
      regions correctly on the original image.
- [ ] Tested against at least 5 images spanning different lighting
      conditions and skin tones — note any obvious bias or failure
      pattern in README, even if not fixed yet.

Once this is solid, move to Phase 2 (visualization polish) or start the
Flutter client — but not before.

---

## 12. Deferred to Later Phases (for context, not to build now)

- Flutter mobile client.
- Spring Boot backend, auth, PostgreSQL, S3/MinIO.
- Rules engine + LLM explanation layer.
- Scan history / longitudinal comparison.
- Trained ML models (PyTorch/ONNX) — only if classical CV heuristics
  prove insufficient after real testing.
- On-device inference, production hardening, bias/perf evaluation at
  scale.

See the original `AI_Face_Analyzer_System_Design.md` for the full
long-term architecture these phases roll up into.
