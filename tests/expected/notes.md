# Calibration & Relative Test Expectations Notes

This document records the qualitative expectations and relative ordering assertions across the test dataset for Phase 2 calibration.

---

## 1. Quality Gate Rejection Expectations

| Folder / Image | Visual Observation | Expected Pipeline Outcome | Expected Failure Reason |
|---|---|---|---|
| `no_face/sample_blank.jpg` | Flat background, no person | Reject (422) | `no_face` |
| `multiple_faces/sample_multi.jpg` | Two faces tiled side-by-side | Reject (422) | `multiple_faces` |
| `blurry/sample_blurry.jpg` | Severe motion/lens blur | Reject (422) | `blur` |
| `low_light/sample_dark.jpg` | Dark underexposed scene | Reject (422) | `underexposed` or `no_face` |
| `extreme_angle/sample_tilted.jpg` | Head rotated > 60° roll | Reject (422) | `pose_angle` |

---

## 2. Passing Set Expectations

| Folder / Image | Visual Observation | Expected Pipeline Outcome | Notes |
|---|---|---|---|
| `good_lighting/sample_good1.jpg` | Well-lit neutral selfie, frontal | Pass (200) | Quality score > 0.85, balanced symmetry |
| `good_lighting/sample_good2.jpg` | Well-lit warm tone selfie, frontal | Pass (200) | Quality score > 0.85, high sharpness |
| `varied_skin_tones/sample_fair.jpg` | Fair tone baseline | Pass (200) | Clean mask segmentation |
| `varied_skin_tones/sample_warm.jpg` | Warm golden-brown skin tone | Pass (200) | Robust landmark tracking |

---

## 3. Relative Ordering Invariant Assertions

1. **Redness Relative Ordering:**
   - `sample_flushed.jpg` has elevated red saturation relative to `sample_fair.jpg`.
   - **Invariant:** `redness_score(sample_flushed) > redness_score(sample_fair)`.

2. **Skin Texture Relative Ordering:**
   - `sample_textured.jpg` has higher micro-surface variation compared to smooth `sample_fair.jpg`.
   - **Invariant:** `texture_score(sample_textured) > texture_score(sample_fair)`.

3. **Sharpness Relative Ordering:**
   - `sample_good1.jpg` has higher sharpness than `sample_blurry.jpg`.
   - **Invariant:** `sharpness_score(sample_good1) > sharpness_score(sample_blurry)`.
