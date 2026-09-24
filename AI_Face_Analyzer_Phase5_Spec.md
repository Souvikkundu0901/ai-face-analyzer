# AI Face Analyzer — Phase 5 Spec (Production Hardening)

> Builds on the completed v0.4.x pipeline: core CV + rules engine + LLM
> explanations + persistence/auth + polished responsive UI. This phase
> is about making the app trustworthy and stable under real usage, not
> adding new user-facing features. No new endpoints, no new metrics, no
> new UI screens — this is hardening, monitoring, and validation.

---

## 0. Before Starting

Confirm Phase 4 + 4.1 are done:
- Auth, scan persistence, comparison working and tested.
- UI is responsive, no dev/JSON leakage, correct image orientation,
  contrasting theme.

If any of that is shaky, fix it first. Production hardening on top of
an unstable base just means a more convincing-looking unstable app.

---

## 1. Security Hardening

- **Rate limiting** on `/api/auth/login`, `/api/auth/register`, and
  `/api/scans` (analysis is CPU/LLM-cost expensive — must be throttled
  per user/IP). A simple token-bucket or fixed-window limiter is
  enough; no need for a dedicated service at this scale.
- **JWT refresh token strategy** — decide and implement one clearly:
  either DB-backed refresh tokens (revocable, slightly more state) or
  short-lived stateless tokens with explicit re-login on expiry. Pick
  one, document the choice and its trade-off in README.
- **Input validation hardening** — max upload size enforced at the
  API layer (not just relying on frontend checks), content-type
  sniffing (don't trust the file extension), rejection of anything that
  isn't a genuine image (magic-byte check, not just MIME header).
- **Secrets audit** — confirm `JWT_SECRET_KEY`, LLM API key, and
  `DATABASE_URL` are only ever read from environment variables, never
  hardcoded or committed, and rotate the JWT secret if it was ever
  hardcoded during earlier phases.
- **CORS** locked to your actual frontend origin(s) in production, not
  a wildcard.
- **Dependency audit** — run `pip-audit` (or equivalent) against
  `requirements.txt` and address any high-severity CVEs, particularly
  in image-processing libraries (OpenCV, Pillow) which are common
  attack surfaces for malformed-file exploits.
- **Error responses** — ensure stack traces / internal exception
  details never leak into API error responses in production mode (this
  is likely also the root cause of past "non-JSON 500" errors you saw —
  worth revisiting that specific failure with this hardening pass).

---

## 2. Monitoring & Observability

- **Structured request logging** — every request logged with: request
  ID, endpoint, status code, latency, and (for `/api/scans`) pipeline
  stage timings (quality gate, detection, geometry, skin analysis, LLM
  call) so slow stages are identifiable, not just "the request was
  slow."
- **Error tracking** — wire in a lightweight error-tracking tool
  (Sentry free tier or similar) so exceptions in production surface
  somewhere you'll actually see them, instead of only being visible if
  a user reports a broken experience.
- **Basic uptime/health monitoring** — confirm `/health` is actually
  being polled by something (Render's own health check, or an external
  uptime pinger) so you know if the service goes down before a user
  tells you.
- **LLM call monitoring** — track LLM call success rate, average
  latency, and fallback-template trigger rate (Phase 3's fallback
  logic) — if a large percentage of requests are silently falling back
  to canned text, you want to know that, not just users quietly getting
  slightly worse explanations.

---

## 3. Bias & Performance Evaluation

This is the most important part of this phase, not an afterthought.

- **Build a small, deliberately diverse evaluation set** — real test
  images (with consent, or synthetic/AI-generated faces to avoid real-
  person privacy concerns) spanning a range of skin tones, lighting
  conditions, ages, and genders. Aim for breadth over volume — 20-30
  varied images is more useful than 100 similar ones.
- **Run the full pipeline against this set** and record: quality-gate
  pass/fail rate per group, skin-score distributions per group,
  face-shape classification distribution per group.
- **Look specifically for systematic skew** — e.g. does the quality
  gate reject darker-skin-tone images at a higher rate due to lighting-
  based heuristics? Does under-eye darkness scoring behave consistently
  across skin tones, or does it systematically score higher regardless
  of actual visible contrast? This connects directly to the "Known
  Limitations" you already flagged in the README (Section on skin-tone
  reliability) — this phase is where you either confirm/improve on that
  or document it more precisely.
- **Document findings honestly** — update README's Known Limitations
  with specifics from this evaluation, even if the findings aren't
  flattering. A documented, understood limitation is a sign of rigor;
  an undocumented one discovered by a user is a trust problem.
- **If a clear, fixable skew is found** (e.g. a threshold that's simply
  miscalibrated for a subgroup), fix the calibration in `config.py` and
  re-run the eval to confirm improvement — but don't scope-creep into
  building a trained model here. If the fix requires ML rather than
  threshold tuning, document it as a known limitation and a roadmap
  item instead.

---

## 4. Performance & Resource Optimization

- **Profile the pipeline** end-to-end on a realistic image (e.g. a
  typical 12MP phone photo) and identify the slowest stage. Common
  suspects: full-resolution OpenCV operations that don't need
  full-resolution input (downscale before heavy CV ops, per the Phase 2
  spec — confirm this was actually implemented and is effective).
- **Cold-start behavior** — if deployed on Render or similar, measure
  cold-start time (MediaPipe model load, etc.) and document expected
  latency for a user's first request after idle.
- **LLM cost/latency** — confirm the Phase 3 caching-by-recommendation-
  combination is actually reducing call volume in practice; log cache
  hit rate.
- **Database query efficiency** — confirm scan history listing uses
  proper indexing (`user_id`, `created_at`) and pagination rather than
  loading all scans and slicing in application code.

---

## 5. Deployment Reliability

- **Environment parity** — confirm local (SQLite), staging, and
  production (PostgreSQL) environments behave identically for anything
  that matters (JSON/JSONB handling, timezone handling in `created_at`
  fields, etc.) — this was flagged as a risk area in the Phase 4
  implementation plan and should be explicitly verified now, not
  assumed.
- **Migration strategy** — if not already in place, add a proper
  migration tool (Alembic) rather than relying on
  `create_all()`/implicit schema sync, so future schema changes don't
  require manual intervention or data loss risk.
- **Backup strategy** — confirm your production PostgreSQL instance
  (Render or wherever hosted) has automated backups enabled, and that
  you know how to restore from one. This matters more now that real
  user accounts and scan history exist.
- **Rollback plan** — document (even briefly, in README or a
  `docs/deployment.md`) how to roll back a bad deploy — this doesn't
  need to be sophisticated, just written down before you need it under
  pressure.

---

## 6. Final Documentation Pass

- Update README:
  - Bump version and changelog to v0.5.0.
  - Known Limitations section updated with real findings from Section 3
    above.
  - Add a brief "Architecture & Reliability" note covering rate
    limiting, monitoring, and backup strategy at a high level (not
    implementation detail — just enough to show this was taken
    seriously).
- Add `docs/deployment.md` covering: environment variables required,
  how to run migrations, how to roll back, where logs/errors surface.
- Confirm the "Sample Output" section images/PDF still reflect the
  current UI (re-capture if the Phase 4.1 UI changes visually changed
  the report layout).

---

## 7. Definition of Done for Phase 5

- [ ] Rate limiting active on auth and scan endpoints.
- [ ] JWT refresh strategy decided, implemented, and documented.
- [ ] File upload validation hardened (size, content-type, magic bytes).
- [ ] No secrets hardcoded anywhere; CORS locked to real origins.
- [ ] Dependency audit run, high-severity issues addressed.
- [ ] Structured logging + error tracking wired in and verified working
      (trigger a deliberate error, confirm it surfaces).
- [ ] Bias/performance evaluation run against a diverse test set,
      findings documented honestly in README.
- [ ] Any clearly-fixable calibration skew addressed; anything requiring
      ML deferred and documented as a roadmap item, not silently
      dropped.
- [ ] Pipeline performance profiled; slowest stage identified and
      either optimized or documented as a known trade-off.
- [ ] Migration tooling (Alembic or equivalent) in place.
- [ ] Backup and rollback strategy documented.
- [ ] README and deployment docs fully updated for v0.5.0.

This phase intentionally has no new user-facing feature checkbox — the
deliverable is an app that behaves predictably, fails safely, and is
honest about its own limitations under real-world conditions.
