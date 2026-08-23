# Rating Performance Guide design

## Purpose

Add a reusable, printable performance view to the generated archive website.
For a selected certificate, a sailor should be able to find target boat speed,
best upwind and downwind angles in both true and apparent wind, and target
velocity made good (VMG) for every published TWS. The same view should also
provide a complete target table and a two-sided AWA/TWA polar.

The first validation certificate is ADELE, EST 467, ORC reference
`04340004VU1`, from the 2026 Estonian dataset.

The feature is named **Rating Performance Guide**. It must not be presented as
an official ORC Speed Guide: the public archive contains the selected rating
envelope, but not the individual sail curves, optimizer outputs, or complete
inputs needed to reproduce ORC's sail-specific product.

## Delivery approach

Use one reusable static page backed by compact generated JSON per VPP year and
country. Do not generate one HTML page per certificate and do not make the
browser load the complete archived country feed.

The canonical page URL is:

```text
/performance/?year=2026&country=EST&ref=04340004VU1
```

An optional URL parameter preserves the wind unit:

```text
&windUnit=kt
```

The certificate browser derives a **Performance guide** link for every row from
VPP year, country, and RefNo. It does not persist a derived URL or availability
flag in certificate CSV. A missing polar is handled by the guide's runtime
unavailable state.

## Generated performance data

For each year and country, generate:

```text
docs/performance/<year>/<country>.json
```

Each record contains only the fields needed by the performance page:

- ORC reference, yacht name, sail number, class, issue date, and certificate
  status;
- VPP year and country;
- official certificate URL;
- `Allowances.WindSpeeds`, `WindAngles`, `Beat`, `BeatAngle`, `Run`,
  `GybeAngle`, and each fixed-angle `R<angle>` array.

Records are keyed by immutable ORC reference and are append-preserving. Current
observations update their corresponding records. Historical observations
backfill records that predate the feature. A certificate is not removed from
the performance data when it leaves the active feed.

Before publishing a record, validate that:

- identity fields include a non-empty ORC reference;
- wind speeds and angles are finite, strictly increasing arrays;
- every required allowance and angle array has the expected wind-speed length;
- all allowance values are finite and greater than zero;
- all beat and gybe angles are finite and lie between 0 and 180 degrees.

An invalid or incomplete record is omitted from performance output. Missing
values are never converted to zero; a link for such a certificate resolves to
the guide's runtime unavailable state.

The JSON is deterministic: records and object keys use stable ordering, and
rendering ends with one newline.

## Calculations

### Published fixed angles

An allowance at a fixed true-wind angle is seconds per nautical mile. Target
boat speed is:

```text
boat speed (kt) = 3600 / allowance (s/NM)
```

### Optimum beat and run

`Beat` and `Run` represent progress along the wind axis, so their reciprocal
speeds are VMG magnitudes:

```text
upwind VMG (kt)   = 3600 / Beat
downwind VMG (kt) = 3600 / Run
```

Target boat speed at the optimum angle is:

```text
beat boat speed = upwind VMG / cos(BeatAngle)
run boat speed  = downwind VMG / abs(cos(GybeAngle))
```

Angles are converted to radians for trigonometric functions. The UI displays
VMG as a positive magnitude and explicitly labels its direction.

### Apparent wind

Given TWS, TWA, and target boat speed, derive apparent wind using the vector
relation described by ORC:

```text
x = TWS * cos(TWA) + boat speed
y = TWS * sin(TWA)
AWA = atan2(y, x)
AWS = sqrt(x² + y²)
```

Normalize AWA into the inclusive 0–180 degree range. AWA is shown because it is
the wind direction observed aboard the boat. AWS may be calculated internally
but is outside the first version's printed tables.

### Published wind speeds

Expose all of the certificate's published TWS conditions without a selection
control. Legacy `tws` URL parameters are ignored and removed when state is
synchronized.

### Units and rounding

All internal wind-speed calculations use knots. Convert wind-speed input and
labels with:

```text
1 kt = 0.514444 m/s
```

The unit control changes TWS only. Target boat speed and VMG always remain in
knots. Display speeds to one decimal place and angles to one decimal place in
the optimum tables. The dense matrix may display AWA as whole degrees for
scanability. Calculations retain unrounded values.

## Sailor-facing page

The screen view has a compact control bar followed by the same two sheets used
for printing.

The control bar contains:

- a `kt` / `m/s` segmented control affecting wind-speed values only;
- a **Print / Save as PDF** action.

Changing the unit updates the URL without navigating.

The header identifies the yacht, sail number, class, issue date, and
certificate status. It links back to the certificate archive and to the
official certificate.

### Page 1: cockpit targets

Print the first sheet in A4 landscape orientation. It contains, in priority
order:

1. One combined target table whose rows are published TWS conditions.
2. The first and last data columns are optimum Beat and Run targets, each
   showing boat speed, TWA, AWA, and VMG.
3. The middle columns are the published fixed TWA values, with each cell
   stacking target boat speed over derived AWA.

### Page 2: dual-angle polar

Print the second sheet in the same A4 landscape job. Render the polar as inline
SVG so it stays sharp on screen and paper.

Follow the useful convention in ORC's Speed Guide explanation:

- wind direction starts at 0 degrees at the top and increases to 180 degrees at
  the bottom;
- the right half plots archived true-wind angles;
- the left half plots the corresponding derived apparent-wind angles;
- radial distance is target boat speed in knots, with a labeled one-knot scale;
- one curve is drawn for each published TWS;
- optimum beat and run endpoints are visibly marked.

Construct each curve from the optimum beat point, the published fixed-angle
points, and the optimum run point. The path must pass through the data points
and must not imply sail-specific crossover curves. Use a print-safe palette and
line-style differences so the chart remains understandable in grayscale.

The chart legend displays TWS in the selected wind unit. Boat-speed radial
labels always remain knots. The wind-flow arrow points from 0 toward 180
degrees. The yacht and sail number use the same compact hierarchy on both
pages.

## Guidance and provenance

Use concise text rather than reproducing ORC's guide. Explain:

- AWA is the angle commonly felt and displayed aboard; TWA describes the
  underlying wind-relative course;
- optimum beat and run angles maximize VMG toward a windward or leeward mark;
- the values are theoretical ORC VPP rating targets, not measured performance;
- sea state, wind shear, crew execution, and instrument calibration can cause
  real performance to differ;
- ORC wind predictions use TWS referenced at 10 metres above the water;
- the page is an independent archive view, not an official ORC Speed Guide and
  not a sail-selection chart.

Link to the archive's data-field documentation, the official certificate, and
ORC's Speed Guide explanation.

## Accessibility and responsive behavior

The target table is the semantic source of truth. The SVG polar supplements it
and has an accessible name and description. Controls have explicit labels and
keyboard focus styles. Do not rely on color alone to distinguish curves.

On narrow screens, controls and target cards stack, tables scroll horizontally,
and the polar scales to the viewport. Printing always uses the two-page A4
landscape layout; screen-only controls and navigation are hidden.

## Error handling

Render a clear non-printing error state when:

- required `year`, `country`, or `ref` parameters are missing or invalid;
- the compact country/year JSON cannot be loaded;
- the requested reference has no valid performance record;
- a TWS input is non-finite or outside the published range.

Error text links back to the appropriate certificate browser when year and
country are known. A bad TWS input preserves the last valid rendered guide and
explains the permitted range rather than blanking the sheets.

## Code boundaries

- `scripts/certificate_history.py` extracts, validates, preserves, and renders
  compact performance records and generates the reusable page and browser
  links.
- `docs/assets/performance-core.mjs` contains pure calculations, interpolation,
  unit conversion, and chart-coordinate helpers with no DOM dependency.
- `docs/assets/performance.js` loads URL state and JSON, renders controls,
  tables, guidance, and SVG, and handles printing.
- `docs/assets/site.css` gains screen, responsive, and print styles for the
  performance view.
- `docs/performance/index.html` and compact JSON files are deterministic
  generated artifacts.

Keep the performance code separate from the certificate-browser filtering code
so both remain independently understandable and testable.

## Verification

Python unit tests cover:

- extraction and strict polar validation;
- deterministic compact JSON;
- preservation of removed and historical references;
- omission of invalid polars and runtime handling for their derived links;
- generated performance page and ADELE-style URLs.

Dependency-free JavaScript tests, run with Node's built-in test runner, cover:

- allowance-to-speed conversion;
- beat/run VMG and target boat-speed calculation;
- ORC apparent-wind conversion;
- exact-point and between-point interpolation;
- range rejection;
- knots/m/s conversion and canonical URL state;
- chart coordinates on both AWA and TWA halves.

Integration checks use ADELE's archived data to confirm representative targets
and verify that the page loads from its shareable URL. Browser QA covers mobile
layout, keyboard controls, print preview, two-page pagination, absence of
clipping, and legibility in grayscale.

## References

- [ORC Speed Guide sample](https://data.orc.org/public/samples/Speed_Guide_Sample.html)
- [ORC Speed Guide explanation](https://data.orc.org/public/samples/Speed_Guide_Explanation.pdf)
- [`docs/data-fields.md`](../../data-fields.md)
- [`docs/performance-guide.md`](../../performance-guide.md)
