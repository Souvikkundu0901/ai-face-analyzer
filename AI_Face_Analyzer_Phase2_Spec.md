# AI Face Analyzer — Phase 2 Spec (Hardening + Visualization)

> Builds on the working Phase 1 pipeline. Goal here is not new features —
> it's making what already works *reliable, testable, and visible* before
> any new capability (Flutter, LLM, recommendations) gets added on top.

---

## 0. Before Starting

Confirm Phase 1 is actually working end-to-end:
- `/api/analyze` returns valid JSON for a normal selfie.
- Quality gate rejects at least one bad-input case correctly.

If either of those isn't reliably true yet, fix that first — don't layer
Phase 2 on a shaky base.

---

## 1. Automated Test Harness (replaces manual eyeballing)

Right now "does it work" is checked by eye. That doesn't scale and won't
catch regressions. Build a small harness:

```text
tests/
├── sample_images/
│   ├── good_lighting/
│   ├── low_light/
│   ├── blurry/
│   ├── multiple_faces/
│   ├── no_face/
│   ├── extreme_angle/
│   └── varied_skin_tones/
├── expected/                  # hand-annotated rough expectations, not exact scores
│   └── notes.md                # e.g. "sample_03: visibly redder cheeks than sample_02, redness_score should be higher"
└── test_pipeline.py
```

- `test_pipeline.py` should run every image through `/api/analyze` (or
  call the pipeline functions directly, faster) and assert:
  - Quality gate rejects the images in `blurry/`, `no_face/`,
    `multiple_faces/`, `extreme_angle/` with the correct reason string.
  - Quality gate passes the images in `good_lighting/`.
  - No unhandled exceptions on any image (even bad ones — should fail
    gracefully with a proper rejection, never a 500).
- Add a **relative ordering test**: if you have two images where one is
  visibly redder/more textured than the other, assert
  `score(image_a) > score(image_b)`. This catches heuristics that are
  just noise even when you don't have ground-truth numbers.
- Run this after every change to `pipeline/`. Wire it into a simple
  `pytest` command, no CI needed yet.

Collect real test images now: at minimum 3–4 different people if
possible (or the same person under different lighting/angles), across a
visible range of skin tones. Testing only on one face under one light
source is the fastest way to ship something that quietly doesn't
generalize.

---

## 2. Calibration Pass on Each Heuristic

For each skin/geometry score, right now the thresholds are best-guess.
Do a deliberate calibration pass:

1. Run the harness images through the pipeline and log raw scores next
   to your own visual judgment (1–5 scale is fine) in
   `tests/expected/notes.md`.
2. Where the score and your judgment clearly diverge, adjust the
   underlying threshold/window/mask logic in `config.py` — not by
   hardcoding per-image fixes, but by finding what's actually miscalibrated
   (e.g. mask too tight and catching hair, redness channel window too
   narrow).
3. Move all magic numbers (blur threshold, brightness bounds, LBP window
   size, blob detector params, shape-classification cutoffs) into
   `config.py` with a comment explaining what each one controls. Nothing
   should be a bare literal inside pipeline logic.

This is the highest-value work in Phase 2 — an uncalibrated heuristic
that "runs without crashing" is not the same as one that produces
meaningful scores.

---

## 3. Debug Overlay — Finish or Upgrade

If the overlay endpoint from Phase 1 wasn't finished, build it now. If
it was, improve it:

- Draw the skin mask boundary (not just landmarks) so you can visually
  confirm eyes/lips/brows are correctly excluded.
- Draw detected spot-like regions as circles sized by their `radius`,
  colored by confidence (e.g. green→red gradient).
- Draw the face-shape classification result as a label overlaid on the
  image, alongside the ratio values used to reach it.
- Add a **quality-gate debug mode**: when an image is rejected, return
  an annotated image showing *why* (e.g. blur heatmap, brightness
  histogram) rather than just a text reason. Optional but very useful
  for calibration.

This overlay is your primary debugging tool going forward — invest in
making it actually legible, not just technically present.

---

## 4. Confidence Scoring — Make It Real

Phase 1 likely has placeholder or naive confidence values. Tighten these:

- **Face shape confidence:** base it on distance from the nearest
  decision boundary in ratio-space, normalized — a face whose jaw/face
  ratio sits right at the oval/round cutoff should score low confidence,
  not the same as a clear-cut case.
- **Region confidence (spots):** base on blob detector's own response
  strength + how much it stands out from local background variance, not
  a flat default.
- **Image quality sub-scores:** make sure `lighting`, `sharpness`, `pose`
  are independently meaningful (i.e. you could look at just one and know
  what's wrong), not all collapsing to the same underlying calculation.

---

## 5. Robustness / Edge Cases

Explicitly handle and test:

- Non-frontal but still valid faces (slight tilt) — should pass with a
  lower pose sub-score and a warning, not a hard rejection, unless
  beyond threshold.
- Glasses, light facial hair, partial hair-over-forehead — shouldn't
  crash the skin mask; document known limitations in README if not
  fully solved.
- Very high-resolution images (e.g. 12MP phone photos) — confirm no
  timeout/memory issue; downscale internally before heavy CV ops if
  needed, but keep original for overlay rendering.
- Non-JPEG/PNG uploads — reject cleanly with a clear error, not a stack
  trace.
- Corrupted/truncated image files — same, clean rejection.

---

## 6. Code & Config Quality Pass

- Add structured logging (`logging` module, not print) at each pipeline
  stage: input received, quality gate result, detection result, timing
  per stage. This will matter a lot once you're debugging real-world
  failures later.
- Add a `pipeline_version` bump mechanism — document in README how/when
  to increment it (any change to thresholds or logic in `pipeline/`
  should bump it).
- Type-hint all pipeline functions; Pydantic models already cover
  request/response, extend that discipline into internal function
  signatures.
- Add a `--verbose` or `DEBUG` env flag that logs raw intermediate
  values (mask coverage %, per-region blob stats) without cluttering
  normal output.

---

## 7. README Update

Update the README to include:

- How to run the test harness and what a passing run looks like.
- Known limitations discovered during calibration (be honest — e.g. "on
  darker skin tones, redness detection is currently less reliable" if
  that's what you find — this is expected at this stage, not a failure).
- How to add a new test image to the harness.
- Current `pipeline_version` and a short changelog of what changed
  since Phase 1.

---

## 8. Definition of Done for Phase 2

- [ ] Automated test harness runs and passes on all `sample_images/`
      subfolders, including correct rejection reasons.
- [ ] All heuristic thresholds live in `config.py`, none hardcoded
      inline.
- [ ] At least one calibration adjustment was made based on comparing
      scores across real varied images (not just synthetic/one-person
      testing).
- [ ] Debug overlay renders mask boundary + spot regions + shape label
      correctly.
- [ ] Confidence scores demonstrably vary based on input clarity (not
      flat/constant across all test images).
- [ ] Pipeline never returns a 500 on any file in `sample_images/`,
      including deliberately bad ones — always a clean rejection or a
      valid result.
- [ ] README reflects current limitations honestly.

Only after this is genuinely done should Phase 3 (recommendation rules +
LLM explanation) or the Flutter client start — adding more layers on top
of an uncalibrated, untested core just compounds the problem later.
