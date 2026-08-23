# Rating Performance Guide design

## Purpose

Add a reusable, printable performance view to the generated archive website.
For a selected certificate and true wind speed (TWS), a sailor should be able
to find the target boat speed, best upwind and downwind angles in both true and
apparent wind, and target velocity made good (VMG). The same view should also
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

Optional URL parameters preserve the selected wind state:

```text
&tws=10&windUnit=kt
```

`tws` is stored canonically in knots even when `windUnit=ms`. This keeps shared
URLs stable across display-unit changes.

The certificate browser adds a **Performance guide** link only when that
certificate has a valid polar record.

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

An invalid or incomplete record is omitted from performance output and receives
no performance link. Missing values are never converted to zero.

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

### Arbitrary wind speeds

Allow selection of any finite TWS within the certificate's published minimum
and maximum. Do not extrapolate beyond that interval.

For a TWS between two published values:

- linearly interpolate each fixed-angle target boat speed;
- linearly interpolate beat VMG, run VMG, BeatAngle, and GybeAngle;
- recalculate optimum boat speeds and every AWA from the interpolated values.

Label interpolated results visibly. Exact published wind speeds are not labeled
as interpolated.

### Units and rounding

All internal wind-speed calculations use knots. Convert wind-speed input and
labels with:

```text
1 kt = 0.514444 m/s
```

The unit control changes TWS only. Target boat speed and VMG always remain in
knots. Display speeds to one decimal place and angles to one decimal place in
the selected-condition cards and optimum tables. The dense matrix may display
AWA as whole degrees for scanability. Calculations retain unrounded values.

## Sailor-facing page

The screen view has a compact control bar followed by the same two sheets used
for printing.

The control bar contains:

- numeric TWS input;
- quick choices for the certificate's published wind speeds;
- a `kt` / `m/s` segmented control affecting wind-speed values only;
- a **Print / Save as PDF** action.

Changing a control updates the URL without navigating. The selected TWS is
validated in both display units and converted to canonical knots before any
calculation.

The header identifies the yacht, sail number, class, VPP year, issue date, and
certificate status. It links back to the certificate archive and to the
official certificate.

### Page 1: cockpit targets

Print the first sheet in A4 landscape orientation. It contains, in priority
order:

1. Two large selected-condition cards: optimum beat and optimum run. Each card
   shows target boat speed, TWA, AWA, and target VMG.
2. Complete published beat and run tables. They include TWS, TWA, AWA, target
   boat speed, and VMG. Separate upwind and downwind groups keep the tables
   readable.
3. A fixed-TWA matrix. Rows are the published true-wind angles and columns are
   the published true-wind speeds. Each cell stacks target boat speed in larger
   type over derived AWA in smaller type.

The selected TWS column is emphasized. If it is interpolated, insert an
emphasized selected column in addition to the published columns and mark it as
interpolated. The landscape layout must remain legible with this additional
column.

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
- the selected curve is emphasized, including a separately drawn interpolated
  curve when needed;
- optimum beat and run endpoints are visibly marked.

Construct each curve from the optimum beat point, the published fixed-angle
points, and the optimum run point. The path must pass through the data points
and must not imply sail-specific crossover curves. Use a print-safe palette and
line-style differences so the chart remains understandable in grayscale.

The chart legend displays TWS in the selected wind unit. Boat-speed radial
labels always remain knots.

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

The target tables are the semantic source of truth. The SVG polar supplements
them and has an accessible name and description. Controls have explicit labels,
keyboard focus styles, and status updates for selection or errors. Do not rely
on color alone to distinguish curves or selected values.

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
- omission of invalid polars and their browser links;
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
