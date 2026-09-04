# AI Face Analyzer — Phase 4 Spec (Scan History + Longitudinal Comparison)

> Builds on the calibrated, rules-gated v0.3.0 pipeline. Adds persistence
> so users can track changes over time — the differentiator the original
> system design doc calls out in Section 14. This is the first phase
> that introduces a database and real user accounts, so scope discipline
> matters more than ever here.

---

## 0. Before Starting

Confirm v0.3.0 is solid:
- Rules engine + LLM explanation layer working, with fallback tested.
- Test harness still passing.
- Pipeline version bumped and consistent across UI and API responses.

If any of that is shaky, fix it first — a database on top of an
unreliable pipeline just means unreliable data persisting forever.

---

## 1. Scope for This Phase

**In scope:**
- Minimal auth (so scans belong to a user).
- PostgreSQL for structured data (users, scans, metrics, reports).
- Object storage for images/overlays *only if retention is enabled* —
  otherwise don't store original photos at all (see Section 6).
- Scan history list + a comparison view between two or more scans.
- Standardized comparison metrics per Section 14 of the original design
  doc.

**Explicitly out of scope — do not build yet:**
- Flutter mobile client (web UI is enough to prove this out).
- Multi-service split (auth/scan/report as separate deployables) — keep
  it a modular monolith.
- Social features, sharing, export beyond the existing PDF.
- Any new CV/skin-analysis capability — this phase is about persistence,
  not new detection features.

---

## 2. Data Model

```text
User
 └── Scan
      ├── ImageMetadata       (dimensions, format, capture timestamp — NOT the image itself by default)
      ├── QualityMetrics
      ├── FaceMetrics
      ├── SkinMetrics
      ├── DetectedRegions
      ├── RecommendationSet   (triggered rule IDs — from Phase 3)
      ├── Report              (LLM explanations + summary + disclaimer)
      └── ModelVersions       (pipeline_version, model_version, timestamp)
```

### Suggested tables

```sql
users (
  id UUID PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)

scans (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  pipeline_version TEXT NOT NULL,
  image_quality JSONB NOT NULL,
  face_metrics JSONB NOT NULL,
  skin_metrics JSONB NOT NULL,
  regions JSONB NOT NULL,
  recommendation_ids TEXT[] NOT NULL,
  report JSONB NOT NULL,
  image_ref TEXT,              -- nullable; only set if retention enabled
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
```

Storing most structured output as JSONB (rather than fully normalizing
every metric into its own column) keeps this migration-friendly as your
schema evolves — you don't want a DB migration every time you tweak a
skin-heuristic field name.

---

## 3. Auth — Keep It Minimal

- Email + password with a hashed password (bcrypt/argon2), JWT for
  session tokens. Don't build OAuth/social login in this phase — it's
  scope creep relative to the actual goal (persistence + comparison).
- Endpoints:
  ```text
  POST /api/auth/register
  POST /api/auth/login
  POST /api/auth/refresh
  ```
- Every `/api/scans*` endpoint requires a valid token; scans are scoped
  to `user_id` — never return another user's scan data.

---

## 4. Scan Endpoints

```text
POST   /api/scans              # run analysis (Phase 1-3 pipeline) + persist result
GET    /api/scans               # list current user's scans, paginated, newest first
GET    /api/scans/{scan_id}     # full detail for one scan
DELETE /api/scans/{scan_id}     # user-initiated deletion (see Section 6)
GET    /api/scans/compare?ids=a,b,c   # comparison view across 2+ scans
```

`POST /api/scans` wraps the existing analyze pipeline — don't duplicate
pipeline logic, just persist its output after it runs.

---

## 5. Comparison Logic

Per Section 14 of the original design doc, standardize comparison
across:

- Spot-like region count
- Redness score
- Pigmentation score
- Texture score
- Under-eye score
- Face-shape stability (did the classified shape change between scans?)
- Image quality consistency (flag if comparing a high-quality scan to a
  low-quality one — the comparison is less meaningful)

**Important:** comparisons should only be presented as meaningful when
capture conditions are reasonably similar. Add a `comparison_confidence`
or `comparability_warning` field that flags cases like:
- Large image-quality gap between the two scans being compared.
- Very different pose/angle scores.
- More than N days apart with no other context (not inherently
  invalid, just worth surfacing).

Don't silently show a clean trend line if the underlying comparison
is shaky — that's the fastest way to give someone a false sense of
"improvement" or "worsening" that's actually just a lighting
difference.

```json
{
  "scans_compared": ["scan_a", "scan_b"],
  "comparability_warning": "Image quality differs significantly between these scans; trend may reflect capture conditions rather than actual change.",
  "deltas": {
    "redness_score": -0.12,
    "pigmentation_score": 0.03,
    "texture_score": -0.05,
    "under_eye_score": 0.0,
    "visible_spots": -1
  },
  "face_shape_stable": true
}
```

---

## 6. Privacy & Retention — Treat as First-Class, Not an Afterthought

This is the phase where privacy stops being theoretical (Section 10 of
the original doc) and becomes real, because you're now persisting data
tied to a real user account.

- **Default: do not store the original image.** Store only the derived
  structured metrics. Add an explicit opt-in toggle if a user wants
  their photo retained (e.g. for a future "compare overlay side by
  side" feature) — off by default.
- If image retention is enabled, encrypt at rest and store in object
  storage (S3/MinIO), never inline in the database.
- `DELETE /api/scans/{scan_id}` must be a real delete — remove the DB
  row and any associated stored image, not a soft-delete flag that
  still allows the data to be queried internally.
- Add `DELETE /api/users/me` (account deletion) that cascades to all
  scans — don't leave orphaned data behind.
- No facial recognition, no embeddings, no cross-user matching — this
  was already a rule in the original doc; it applies with more force
  now that there's a persistent store to misuse.
- Log access to scan data (who accessed what, when) even if it's just
  the user themselves for now — you'll want this audit trail later if
  you ever add admin/support tooling.

---

## 7. Web UI Additions

- **Scan history list** — thumbnail-free (per default no-image-storage
  rule) cards showing date, overall score, face shape, and top
  recommendation, newest first.
- **Comparison view** — select two or more scans, show delta chart per
  metric (redness/pigmentation/texture/under-eye/spots over time), with
  the `comparability_warning` surfaced prominently if present, not
  buried.
- **Account/delete controls** — visible "Delete this scan" and "Delete
  my account and all data" actions, not hidden in a settings submenu.

---

## 8. Testing

- Unit test comparison-delta calculation with known score pairs.
- Test `comparability_warning` triggers correctly on mismatched quality/
  pose scores.
- Test that deleting a scan actually removes it from the DB (not just
  hidden from list queries).
- Test that one user cannot retrieve or compare another user's scans
  (authorization test, not just a UI assumption).
- Load a user with 10+ scans and confirm history pagination works
  correctly.

---

## 9. Definition of Done for Phase 4

- [ ] Auth (register/login/refresh) working, scans scoped per user.
- [ ] Scans persist to PostgreSQL with full structured output from the
      Phase 1-3 pipeline.
- [ ] No image storage by default; opt-in toggle works if implemented.
- [ ] Scan history list and comparison view working in the web UI.
- [ ] Comparison logic includes `comparability_warning` for mismatched
      capture conditions — verified with a deliberately mismatched pair.
- [ ] Scan deletion and account deletion are real deletes, tested.
- [ ] Authorization tested — one user cannot access another's data.
- [ ] README updated with new endpoints, auth flow, and privacy/
      retention behavior documented plainly for anyone reading the repo.

Only after this is solid should the Flutter client or production
hardening (Phase 5) begin — building a mobile client against a
half-finished persistence layer just means redoing work later.
