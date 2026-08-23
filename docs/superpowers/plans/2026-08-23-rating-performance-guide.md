# Rating Performance Guide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable, shareable, two-page printable Rating Performance Guide backed by compact archived polar data, validated with ADELE EST 467.

**Architecture:** Extend the deterministic Python site generator to preserve a compact polar record per certificate in country/year JSON. A standalone browser page loads one record by URL and delegates all numerical work to a dependency-free ES module, while DOM code renders the cockpit tables and mirrored SVG polar. Existing archive pages link into the reusable guide only for certificates with valid polar data.

**Tech Stack:** Python 3.11+ standard library, semantic HTML, CSS print media, browser JavaScript ES modules, SVG, Node built-in test runner

**Spec:** `docs/superpowers/specs/2026-08-23-rating-performance-guide-design.md`

> **Revision:** The shipped follow-up removes TWS selection and interpolation
> from the UI, merges the three target tables into one TWS-row table, and
> derives guide links at runtime without a CSV URL or availability field. The
> task transcript below records the original implementation sequence.

## Global Constraints

- Name the feature **Rating Performance Guide**, never **ORC Speed Guide**.
- Generate one reusable page plus `docs/performance/<year>/<country>.json`; do not generate per-certificate HTML.
- Keep all internal TWS values in knots and convert TWS display with `1 kt = 0.514444 m/s`.
- Target boat speed and VMG always remain knots.
- Never extrapolate outside the certificate's published TWS interval.
- Preserve performance records after certificates leave the active feed.
- Omit malformed polar records and never coerce missing values to zero.
- Use only repository and platform dependencies; add no runtime package dependency.
- Print exactly two A4 landscape sheets, with semantic tables as the accessible source of truth.

---

## File structure

- Modify `scripts/certificate_history.py`: extract and validate compact polars, preserve them across observations, generate the reusable HTML shell and JSON, and add certificate-browser guide links.
- Modify `tests/test_certificate_history.py`: test validation, deterministic JSON, preservation, generated page, and conditional links.
- Create `docs/assets/performance-core.mjs`: pure speed, VMG, apparent-wind, interpolation, unit, URL-state, and polar-coordinate functions.
- Create `tests/performance-core.test.mjs`: dependency-free numerical and interpolation tests, including ADELE reference values.
- Modify `.github/workflows/test.yml`: run Node's built-in test runner after Python tests.
- Create `docs/assets/performance.js`: load one performance record, manage controls and URL state, render tables and error states, and call the polar renderer.
- Modify `docs/assets/site.css`: style the performance controls, two sheets, tables, SVG, responsive state, and two-page print output.
- Generate `docs/performance/index.html`: reusable semantic shell.
- Generate `docs/performance/<year>/<country>.json`: compact, stable performance archives.
- Modify `README.md` and `docs/performance-guide.md`: document the shipped guide and its limitations.
- Create `scripts/generate_site.py`: regenerate GitHub Pages artifacts from committed archive data without network access.
- Create `tests/test_generate_site.py`: verify deterministic offline site generation.

---

### Task 1: Compact performance archive and certificate links

**Files:**
- Modify: `scripts/certificate_history.py`
- Modify: `tests/test_certificate_history.py`

**Interfaces:**
- Consumes: `build_history_site(site_dir, observations, observed_on, historical_observations=())` with existing observation tuple shapes.
- Produces: `extract_performance_record(year: int, country: str, boat: dict, status: str) -> dict | None`, generated `performance/<year>/<country>.json`, generated `performance/index.html`, and `performance_url(year: int, country: str, ref_no: str) -> str`.

- [ ] **Step 1: Add a valid-polar fixture and failing extraction tests**

Add a `polar_boat()` helper with two wind speeds and two fixed angles, then tests equivalent to:

```python
def polar_boat(ref_no="A"):
    return {
        "RefNo": ref_no,
        "SailNo": "EST 467",
        "YachtName": "ADELE",
        "Class": "First 34.7",
        "IssueDate": "2026-07-31T09:26:27Z",
        "Allowances": {
            "WindSpeeds": [8, 10],
            "WindAngles": [52, 60],
            "Beat": [895.5, 793.2],
            "BeatAngle": [41.6, 40.0],
            "Run": [797.6, 672.0],
            "GybeAngle": [149.8, 152.5],
            "R52": [601.0, 548.3],
            "R60": [576.7, 532.9],
        },
    }

def test_extracts_only_valid_compact_performance_fields(self):
    record = extract_performance_record(2026, "EST", polar_boat(), "active")
    self.assertEqual("A", record["ref_no"])
    self.assertEqual([8, 10], record["allowances"]["wind_speeds"])
    self.assertNotIn("GPH", record)

def test_rejects_incomplete_or_non_finite_polar(self):
    boat = polar_boat()
    boat["Allowances"]["R60"] = [576.7]
    self.assertIsNone(extract_performance_record(2026, "EST", boat, "active"))
```

- [ ] **Step 2: Run the focused tests and confirm RED**

Run: `python -m unittest tests.test_certificate_history.CertificateHistoryTests.test_extracts_only_valid_compact_performance_fields tests.test_certificate_history.CertificateHistoryTests.test_rejects_incomplete_or_non_finite_polar -v`

Expected: import failure because `extract_performance_record` does not exist.

- [ ] **Step 3: Implement strict extraction and deterministic serialization**

Add finite-number and strictly-increasing helpers. Normalize keys to the browser schema:

```python
{
    "ref_no": ref_no,
    "sail_no": _text(boat.get("SailNo")),
    "yacht_name": _text(boat.get("YachtName")),
    "class": _text(boat.get("Class")),
    "issue_date": _text(boat.get("IssueDate")),
    "status": status,
    "vpp_year": year,
    "country": country,
    "certificate_url": certificate_url(ref_no),
    "allowances": {
        "wind_speeds": wind_speeds,
        "wind_angles": wind_angles,
        "beat": beat,
        "beat_angle": beat_angle,
        "run": run,
        "gybe_angle": gybe_angle,
        "fixed": {str(angle): allowances[f"R{angle}"] for angle in wind_angles},
    },
}
```

Return `None` for booleans, non-finite values, non-increasing axes, non-positive allowances, length mismatches, missing `R<angle>` arrays, and beat/gybe angles outside 0–180 degrees. Serialize as `{"records":[...]}` with `json.dumps(..., ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"`.

- [ ] **Step 4: Add failing site-generation and preservation tests**

Cover all of these assertions:

```python
write_plan(build_history_site(site_dir, [(2026, "EST", [polar_boat()])], "2026-08-22"))
payload = json.loads((site_dir / "performance" / "2026" / "EST.json").read_text())
self.assertEqual(["A"], [record["ref_no"] for record in payload["records"]])
self.assertTrue((site_dir / "performance" / "index.html").exists())
self.assertIn("Performance guide", (site_dir / "certificates" / "2026" / "index.html").read_text())

write_plan(build_history_site(site_dir, [(2026, "EST", [])], "2026-08-23"))
payload = json.loads((site_dir / "performance" / "2026" / "EST.json").read_text())
self.assertEqual("archived", payload["records"][0]["status"])
```

Also assert that a boat without valid `Allowances` gets no link and that a historical polar passed through `historical_observations` is backfilled.

- [ ] **Step 5: Run the site-generation tests and confirm RED**

Run: `python -m unittest tests.test_certificate_history -v`

Expected: new performance files and links are absent.

- [ ] **Step 6: Generate and preserve compact performance data**

Materialize both observation iterables at the top of `build_history_site` so history and performance passes can consume them. Load existing compact JSON files keyed by `(year, country, ref_no)`, merge historical valid polars first, merge active polars second, and derive current status from certificate history. Never delete an existing valid record. Generate `performance/index.html` with a performance-specific module script and data attributes required by Task 3.

In certificate rows, render both actions when valid performance exists:

```html
<a class="performance-link" href="../../../performance/?year=2026&amp;country=EST&amp;ref=A">Performance guide</a>
<a class="certificate-link" href="…">Open certificate</a>
```

Pass the set of valid `(year, country, ref_no)` keys into `_render_year_page`; URL-encode all query values.

- [ ] **Step 7: Run Python tests and confirm GREEN**

Run: `python -m unittest tests.test_certificate_history tests.test_update_archive -v`

Expected: all tests pass, including unchanged archive-update behavior.

- [ ] **Step 8: Commit the data layer**

```bash
git add scripts/certificate_history.py tests/test_certificate_history.py
git commit -m "Add compact performance archive generation"
```

---

### Task 2: Pure performance calculations and interpolation

**Files:**
- Create: `docs/assets/performance-core.mjs`
- Create: `tests/performance-core.test.mjs`
- Modify: `.github/workflows/test.yml`

**Interfaces:**
- Consumes: one compact `record.allowances` object from Task 1.
- Produces: `allowanceToSpeed`, `apparentWind`, `publishedCondition`, `conditionAtTws`, `convertWindSpeed`, `formatWindSpeed`, `polarPoint`, `readGuideState`, and `writeGuideState` named exports.

- [ ] **Step 1: Write failing numerical tests using ADELE values**

Use Node's `node:test` and `node:assert/strict`:

```javascript
test("ADELE 10 kt beat and run targets", () => {
  const condition = publishedCondition(adeleAllowances, 3);
  assert.equal(condition.beat.vmg.toFixed(2), "4.54");
  assert.equal(condition.beat.boatSpeed.toFixed(2), "5.92");
  assert.equal(condition.beat.awa.toFixed(1), "25.3");
  assert.equal(condition.run.vmg.toFixed(2), "5.36");
  assert.equal(condition.run.boatSpeed.toFixed(2), "6.04");
  assert.equal(condition.run.awa.toFixed(1), "121.5");
});

test("fixed 10 kt 52 degree target", () => {
  const condition = publishedCondition(adeleAllowances, 3);
  assert.equal(condition.fixed[0].boatSpeed.toFixed(2), "6.57");
  assert.equal(condition.fixed[0].awa.toFixed(1), "31.8");
});
```

Add tests for exact published lookup, midpoint linear interpolation, no extrapolation, `kt`/`m/s` conversion, negative/non-finite rejection, AWA normalization, URL state, and left/right `polarPoint` symmetry.

- [ ] **Step 2: Run Node tests and confirm RED**

Run: `node --test tests/performance-core.test.mjs`

Expected: module-not-found failure for `performance-core.mjs`.

- [ ] **Step 3: Implement the pure calculation module**

Use these return shapes:

```javascript
publishedCondition(allowances, index) => {
  tws,
  interpolated: false,
  beat: {twa, awa, boatSpeed, vmg},
  run: {twa, awa, boatSpeed, vmg},
  fixed: [{twa, awa, boatSpeed, vmg}],
}

conditionAtTws(allowances, tws) => same shape with interpolated true or false
apparentWind(tws, twa, boatSpeed) => {awa, aws}
polarPoint(angleDegrees, boatSpeed, side, scale) => {x, y}
```

Interpolate fixed target speeds, beat/run VMG, and beat/run angles between bracketing indices. Recalculate optimum target speed and all AWA values after interpolation. Throw `RangeError` beyond the published range and `TypeError` for non-finite inputs. `readGuideState(URLSearchParams)` accepts only `windUnit=kt|ms`, while `writeGuideState` always writes canonical knot TWS.

- [ ] **Step 4: Run Node tests and confirm GREEN**

Run: `node --test tests/performance-core.test.mjs`

Expected: all numerical, interpolation, unit, URL, and coordinate tests pass.

- [ ] **Step 5: Add Node verification to CI**

Add `actions/setup-node@v6` with Node 24 and run:

```yaml
- run: node --test tests/performance-core.test.mjs
```

Run: `python -m unittest discover -s tests -v`

Run: `node --test tests/performance-core.test.mjs`

Expected: both suites pass locally.

- [ ] **Step 6: Commit the calculation core**

```bash
git add docs/assets/performance-core.mjs tests/performance-core.test.mjs .github/workflows/test.yml
git commit -m "Add performance target calculations"
```

---

### Task 3: Reusable guide controls and cockpit tables

**Files:**
- Create: `docs/assets/performance.js`
- Modify: `scripts/certificate_history.py`
- Modify: `docs/assets/site.css`
- Modify: `tests/test_certificate_history.py`

**Interfaces:**
- Consumes: Task 1 HTML shell and compact JSON; Task 2 calculation exports.
- Produces: a loaded guide state, semantic selected-condition cards, optimum tables, fixed-angle matrix, URL synchronization, and stable DOM hooks used by Task 4.

- [ ] **Step 1: Add failing generated-shell assertions**

Assert that `performance/index.html` contains the module entry point and semantic containers:

```python
self.assertIn('type="module" src="../assets/performance.js"', page)
self.assertIn('id="performance-controls"', page)
self.assertIn('id="guide-error" role="alert"', page)
self.assertIn('id="cockpit-sheet"', page)
self.assertIn('id="polar-sheet"', page)
self.assertIn('id="target-matrix"', page)
```

- [ ] **Step 2: Run the focused shell test and confirm RED**

Run: `python -m unittest tests.test_certificate_history.CertificateHistoryTests.test_generates_performance_page_shell -v`

Expected: required semantic hooks are missing.

- [ ] **Step 3: Render the final semantic HTML shell**

Generate a header, labeled numeric input, unit fieldset, published-speed button container, print button, live validation status, error alert, and two `<section class="performance-sheet">` elements. Put real table headings in the shell and let JavaScript populate only `<tbody>` and matrix columns. Add a noscript message. Keep all copy aligned with the spec's independent-archive language.

- [ ] **Step 4: Implement loading, validation, controls, and URL state**

In `performance.js`:

1. Read `year`, `country`, `ref`, `tws`, and `windUnit`.
2. Validate year as four digits, country as 2–3 uppercase ASCII letters, and non-empty ref.
3. Fetch `./<year>/<country>.json` and find the exact reference.
4. Default TWS to 10 kt when within range, otherwise the middle published value.
5. Render published quick buttons in the selected wind unit.
6. Convert input when the unit changes without changing canonical TWS.
7. On a valid selection, call `conditionAtTws`, update the URL, and retain that render as `lastValidCondition`.
8. On invalid TWS, show the allowed range and keep the last valid sheets visible.
9. Call `window.print()` only from the explicit print button.

Use `textContent`, `createElement`, and explicit attributes; do not inject archive values with `innerHTML`.

- [ ] **Step 5: Render the page-one cockpit content**

Render:

- two selected cards with boat speed, TWA, AWA, and VMG;
- separate published beat and run tables with TWS, TWA, AWA, boat speed, VMG;
- a matrix whose rows are fixed TWA and whose columns are all published TWS plus the selected interpolated TWS when applicable;
- each matrix cell as `<strong>6.6 kt</strong><small>AWA 32°</small>`;
- `data-selected="true"` on the active column cells and an **Interpolated** label when applicable.

All TWS headings use `formatWindSpeed`; every boat-speed and VMG value uses knots.

- [ ] **Step 6: Add screen and responsive styles**

Extend the existing visual language with a sticky `.performance-controls`, white `.performance-sheet` surfaces, high-contrast target cards, scrollable table wrappers, stacked speed/AWA matrix cells, clear focus-visible rules, and a mobile breakpoint that stacks cards and controls. Do not add print rules until Task 4.

- [ ] **Step 7: Run static tests and a local smoke server**

Run: `python -m unittest discover -s tests -v`

Run: `node --test tests/performance-core.test.mjs`

Run: `python -m http.server 8000 --directory docs`

Open: `http://localhost:8000/performance/?year=2026&country=EST&ref=04340004VU1&tws=10&windUnit=kt`

Expected: ADELE identity and both page-one tables render; controls update URL and values; invalid input leaves the last valid guide visible.

- [ ] **Step 8: Commit the cockpit guide**

```bash
git add scripts/certificate_history.py tests/test_certificate_history.py docs/assets/performance.js docs/assets/site.css
git commit -m "Build printable cockpit target tables"
```

---

### Task 4: Mirrored AWA/TWA polar and two-page print layout

**Files:**
- Modify: `docs/assets/performance.js`
- Modify: `docs/assets/site.css`
- Modify: `tests/performance-core.test.mjs`

**Interfaces:**
- Consumes: Task 2 `polarPoint` and Task 3 `renderGuide(record, condition, state)` flow.
- Produces: `renderPolar(svg, record, selectedCondition, windUnit)` and a two-page A4 landscape print layout.

- [ ] **Step 1: Add coordinate and series tests for both chart halves**

Assert that 0 degrees plots at the top, 90 degrees at the outer horizontal axis, 180 degrees at the bottom, AWA maps left, TWA maps right, and radial distance scales linearly in boat-speed knots. Add a test that a published condition yields the ordered point series `[beat, ...fixed, run]` and that AWA-side points use each point's derived AWA.

- [ ] **Step 2: Run Node tests and confirm RED for the new series helper**

Run: `node --test tests/performance-core.test.mjs`

Expected: missing `polarSeries` export or mismatched ordering.

- [ ] **Step 3: Implement polar series and SVG rendering**

Export `polarSeries(condition)` from the core module. In DOM code, build SVG elements with `createElementNS`:

- concentric one-knot rings up to `ceil(maxBoatSpeed)`;
- angle spokes and labels at 0, 15, 30, 45, 60, 75, 90, 120, 150, and 180 degrees;
- `AWA` and `TWA` side labels plus a wind arrow;
- one right-hand TWA polyline and one left-hand AWA polyline per published TWS;
- an emphasized selected/interpolated pair drawn last;
- beat/run endpoint markers;
- a legend with converted TWS labels and distinct dash patterns.

Give the SVG a `<title>` and `<desc>` identifying the yacht and explaining that radial distance is boat speed in knots. Never label curves by sail type.

- [ ] **Step 4: Implement print-safe two-page CSS**

Add:

```css
@page { size: A4 landscape; margin: 8mm; }
@media print {
  .screen-only, .site-header, .performance-controls { display: none !important; }
  .performance-sheet { break-after: page; box-shadow: none; margin: 0; min-height: 0; }
  .performance-sheet:last-child { break-after: auto; }
  #target-matrix { break-inside: avoid; }
  .polar-curve { print-color-adjust: exact; }
}
```

Use both color and dash pattern for curve identity. Ensure sheet content fits without scaling below legible table text.

- [ ] **Step 5: Verify the browser and print rendering**

Serve `docs` and inspect ADELE at 10 kt and at an interpolated 11 kt, in both `kt` and `m/s`. Verify narrow viewport horizontal table behavior, keyboard focus, and error copy. Open print preview and confirm exactly two landscape pages, no clipped matrix columns, sharp SVG, grayscale-distinguishable curves, hidden controls, and visible provenance.

- [ ] **Step 6: Run all automated tests**

Run: `python -m unittest discover -s tests -v`

Run: `node --test tests/performance-core.test.mjs`

Expected: all tests pass.

- [ ] **Step 7: Commit the polar and print layout**

```bash
git add docs/assets/performance-core.mjs docs/assets/performance.js docs/assets/site.css tests/performance-core.test.mjs
git commit -m "Add dual-angle polar and print layout"
```

---

### Task 5: Regenerate archive artifacts and complete end-to-end verification

**Files:**
- Create: `scripts/generate_site.py`
- Create: `tests/test_generate_site.py`
- Modify: `README.md`
- Modify: `docs/performance-guide.md`
- Generate: `docs/index.html`
- Generate: `docs/certificates/*/index.html`
- Generate: `docs/performance/index.html`
- Generate: `docs/performance/*/*.json`

**Interfaces:**
- Consumes: completed generator and browser assets from Tasks 1–4 plus archived `data/**/*.json`.
- Produces: committed GitHub Pages artifacts and documentation for the live feature.

- [ ] **Step 1: Add a local deterministic site-regeneration command**

Create `scripts/generate_site.py` with:

```python
def generate_site(
    data_dir: Path,
    site_dir: Path,
    observed_on: str,
    history_loader: Callable[[Path], Iterable[HistoryObservation]] = load_git_observations,
) -> list[Path]:
    """Regenerate deterministic site files from committed JSON without network access."""
```

It reads every `data/<year>/<country>.json`, validates that `rms` is a list,
calls `build_history_site`, and writes only changed files. Its CLI requires
`--observed-on YYYY-MM-DD` so generation from a fixed checkout is reproducible.
Add `tests/test_generate_site.py` that generates twice from a temporary ADELE
dataset using the same date and asserts byte-identical output and no network
access.

- [ ] **Step 2: Regenerate all site artifacts from archived data**

Run the local generation command against `data/` and `docs/`. Confirm that ADELE exists in `docs/performance/2026/EST.json` with reference `04340004VU1` and that the 2026 certificate page links to the reusable guide.

- [ ] **Step 3: Update feature documentation**

In `README.md`, add the guide URL pattern, unit behavior, and printable two-page description. Convert `docs/performance-guide.md` from a future-feasibility note to current feature documentation while retaining the exact limitation that public RMS data cannot reconstruct sail-specific ORC Speed Guide curves.

- [ ] **Step 4: Run the complete verification suite**

Run: `python -m unittest discover -s tests -v`

Run: `node --test tests/performance-core.test.mjs`

Run: `git diff --check`

Expected: all tests pass and no whitespace errors are reported.

- [ ] **Step 5: Audit ADELE against the specification**

Verify from generated data and rendered output:

- identity is ADELE / EST 467 / First 34.7 / `04340004VU1`;
- 10 kt beat target is approximately 5.9 kt boat speed, 40.0° TWA, 25.3° AWA, and 4.5 kt VMG;
- 10 kt run target is approximately 6.0 kt boat speed, 152.5° TWA, 121.5° AWA, and 5.4 kt VMG;
- the fixed-angle matrix contains both target speed and AWA;
- 11 kt is visibly interpolated;
- changing TWS display to m/s does not change boat-speed or VMG units;
- the mirrored polar has AWA left, TWA right, all published curves, and selected endpoints;
- print preview contains exactly two A4 landscape pages.

- [ ] **Step 6: Commit generated artifacts and documentation**

```bash
git add README.md docs scripts/generate_site.py tests/test_generate_site.py
git commit -m "Publish rating performance guides"
```
