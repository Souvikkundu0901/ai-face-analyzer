# AI Face Analyzer — Phase 4.1 Spec (UI/UX Polish & Frontend Hardening)

> This is a frontend-focused pass, not a new pipeline phase. Goal: make
> the app look and behave like a finished consumer product, not a
> developer tool. No backend/pipeline logic changes required — this is
> about what the frontend shows and how it looks/responds.

---

## 0. Why This Matters

The pipeline and rules engine are solid, but right now the frontend
still reads like a debug console: raw pipeline version numbers, JSON-ish
labels, a warning icon that fires before there's even an image, and a
mirrored camera preview that doesn't match the actual analyzed photo.
None of that belongs in front of a real user. This pass closes that gap.

---

## 1. Fix: Camera Preview Should NOT Be Mirrored

**Problem:** Live camera preview (and/or the captured photo) is
currently flipped horizontally, like a normal front-camera "selfie
mirror." But the actual image sent to the backend and analyzed is
presumably not flipped, so what the user sees during capture doesn't
match what gets analyzed — which is confusing and can make the debug
overlay/landmarks look mismatched to the user's expectation.

**Fix:**
- If using `getUserMedia` for a live camera feed, remove any
  `transform: scaleX(-1)` / `-webkit-transform: scaleX(-1)` CSS applied
  to the `<video>` element used for preview.
- Ensure the **captured frame** drawn to `<canvas>` (before upload) is
  taken from the unmirrored feed, or is explicitly un-flipped before
  being converted to a blob for upload.
- The **uploaded/original photo view** and the **debug overlay view**
  must both show the image in its true orientation — exactly as
  captured, not mirrored — so landmark overlays line up visually with
  what the user expects (e.g. a mole on their actual left cheek should
  appear on the left side of the image as displayed, not flipped).
- Test explicitly: capture a photo of yourself holding up something
  asymmetric (e.g. a piece of paper with text, or raise your left hand)
  and confirm the displayed/analyzed image matches your real-world
  orientation, not a mirror image.

---

## 2. Fix: Hide Developer/Debug Details from the Frontend

**Problem:** The UI currently exposes internal implementation details
that mean nothing to an end user and undercut the "finished product"
feel — e.g. `pipeline_version` / "Pipeline v0.4.0 Active" badges, raw
recommendation rule IDs (`REDNESS_MODERATE`, `UNDER_EYE_DARK`), scan
UUIDs, and any other backend/JSON-shaped text rendered directly in the
UI.

**Fix:**
- Remove the "Pipeline vX.X.X Active" badge from the visible UI
  entirely, or move it to a `title` tooltip / hidden dev-mode panel that
  only renders when a `?debug=true` query param or similar is present —
  never shown by default.
- Remove raw rule ID text (`REDNESS_MODERATE`, `PIGMENTATION_VARIATION`,
  `UNDER_EYE_DARK`, etc.) from recommendation cards. Keep the
  human-readable title ("Moderate Redness") and the LLM explanation
  text only. If you want a technical/debug view for yourself, gate it
  behind the same `?debug=true` flag.
- Remove the visible Scan ID (UUID) from the main report view. If
  needed for support/reference purposes, it can live in fine print at
  the very bottom of an exported PDF only, not in the primary UI.
- Audit the entire results view for any other field name, snake_case
  text, internal score key, or raw JSON fragment that leaked into
  rendered text, and replace with a proper human-readable label.
- General rule going forward: **if a piece of text looks like a
  variable name or an internal identifier, it does not belong in the
  default user-facing UI.**

---

## 3. Fix: Quality-Gate Warning Should Only Appear After an Image Is Provided

**Problem:** The ⚠️ warning ("Slight head angle detected; center
alignment gives the most consistent measurements") and/or the quality
gate card in general appears to be showing before any image has
actually been uploaded/captured — i.e. it's present as a default/empty
state rather than only appearing as a real result of analyzing an
actual photo.

**Fix:**
- The entire **Image Quality Gate** card (and any warning icon/text
  within it) must only render **after** a scan has been run on an
  actual uploaded/captured image and a real response has come back from
  the backend.
- Before an image is provided: show the upload/capture prompt only.
  No score cards, no quality gate card, no warning icons, no
  placeholder data of any kind.
- After an image is analyzed: show the real results, including the
  quality gate card **only if there's an actual warning or the gate
  info is relevant to display** — i.e. don't show a hardcoded/sample
  warning that doesn't reflect the actual image just analyzed.
- If the current warning message is coming from a hardcoded default in
  the frontend template rather than the live API response, that's the
  bug — the warning text must be sourced dynamically from the
  `image_quality.warnings` (or equivalent) field in the actual response
  for that specific scan, and must be absent/empty when the real
  response has no warnings.

---

## 4. Theme: Contrasting Color Palette (Not All-Pink)

**Problem:** Current theme relies heavily on pink for nearly everything
(header accents, buttons, card highlights, badges, progress bars) —
visually flat and low-contrast in places, and doesn't clearly
distinguish different states (good/warning/elevated/optimal) from each
other or from neutral UI chrome.

**Fix — establish a real palette with pink as an accent, not the whole
theme:**

```text
Primary accent:      Pink/Magenta   #EC4899 (or current brand pink) — used sparingly: primary CTA button, active tab, brand mark only
Secondary/neutral:   Deep navy/charcoal  #1E1B2E or #111827 — headers, primary text, nav
Background:          Off-white/near-black depending on light/dark mode — NOT pink-tinted
Success/optimal:     Green    #10B981 — "Optimal" skin scores, passed quality gate
Warning/elevated:    Amber/orange  #F59E0B — "Elevated" / "Moderate" scores
Danger/high:         Red   #EF4444 — reserved for genuinely high-severity flags only
Info/neutral data:   Slate/blue-gray  #64748B — geometry ratios, neutral metadata
```

- Score/status badges ("Optimal", "Elevated", "Moderate") must use
  color semantically (green/amber/red-ish) rather than all being pink
  regardless of value — right now "Optimal (11%)" and "Elevated (97%)"
  reportedly render in the same pink tone, which defeats the purpose of
  an at-a-glance status color.
- Keep pink as the **brand accent**: logo mark, primary button, active
  state indicators, and section icons — not the color of every score,
  every card border, and every badge.
- Ensure sufficient contrast ratio (WCAG AA minimum, 4.5:1 for body
  text) between text and background in both the new palette and any
  existing dark-mode variant.

---

## 5. Responsive Web Design

**Problem:** Layout is currently built as a fixed two-column dashboard
(left: capture/upload, right: report) that doesn't appear to adapt
below desktop widths.

**Fix — implement proper responsive breakpoints:**

- **Desktop (≥1024px):** current two-column layout is fine — capture
  panel left, report right.
- **Tablet (768px–1023px):** stack to single column; capture/upload
  panel on top, full-width report below. Score cards can remain in a
  2-column grid.
- **Mobile (<768px):**
  - Single column throughout.
  - Score cards (Symmetry, Face Shape, Visible Spots, Skin Clarity)
    stack to 1 or 2 per row, not squeezed into 4 across.
  - Skin characteristic bars (Redness, Pigmentation, etc.) remain
    full-width and legible — don't shrink text below ~14px.
  - "Analyze Face" / "Use Camera" buttons remain thumb-reachable
    (adequate tap target size, ~44px minimum height).
  - Debug Overlay / Original Photo toggle remains usable, not
    cut off or overlapping.
  - Recommendation cards stack fully, no horizontal scrolling required
    anywhere on the page.
- Use CSS Grid/Flexbox with `minmax()`/`auto-fit` or standard media
  query breakpoints — whichever matches the existing frontend's
  approach (plain CSS, Tailwind, etc.).
- Test on at least: a real or emulated mobile viewport (~375px wide),
  a tablet viewport (~768px), and desktop (~1440px). No element should
  overflow its container or require horizontal scrolling at any of
  these widths.
- Camera capture flow specifically must work on mobile — verify
  `getUserMedia` permission flow and preview rendering on a real mobile
  browser (iOS Safari and Android Chrome ideally), not just resized
  desktop Chrome.

---

## 6. Definition of Done

- [ ] Captured/uploaded/overlay images display in true (non-mirrored)
      orientation, verified with an asymmetric test photo.
- [ ] No pipeline version, rule IDs, scan UUIDs, or other raw
      developer/JSON-shaped text visible anywhere in the default UI.
- [ ] Quality-gate card and any warning text render only after a real
      scan result comes back, and only when the actual response
      contains a warning — never as a default/placeholder state.
- [ ] Color palette uses pink as an accent only; status badges
      (Optimal/Elevated/Moderate/High) use distinct semantic colors
      (green/amber/red) rather than uniform pink.
- [ ] Layout is verified functional and visually correct at ~375px,
      ~768px, and ~1440px widths with no horizontal scrolling or
      overlapping elements.
- [ ] Camera capture and upload flow both tested on an actual mobile
      browser, not just a resized desktop window.
- [ ] All interactive elements (buttons, toggles, tabs) meet a minimum
      ~44px touch target on mobile.
