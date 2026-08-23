# ORC rating-data fields

<!-- markdownlint-disable MD013 -->

This reference describes the fields observed in the archived ORC `Family=1`
JSON and CSV feeds. It is a consumer guide, not a versioned schema published by
ORC: fields and scoring options may change with a new VPP year. Preserve unknown
fields and prefer the JSON `ScoringOptions` metadata when interpreting scoring
coefficients.

## Units and scoring conventions

Unless a field says otherwise:

- lengths are metres (`m`)
- areas are square metres (`m²`)
- weights and displacements are kilograms (`kg`)
- wind speeds are knots (`kt`)
- angles are degrees
- Time-on-Distance (`TOD` or `ToD`) values are seconds per nautical mile
  (`s/NM`)
- Time-on-Time (`TOT` or `ToT`) values are dimensionless elapsed-time
  multipliers
- Polar Curve Scoring (`PCS`) values are arrays of time allowances in `s/NM`

For a polar time allowance `t` in `s/NM`, the corresponding boat speed is
`3600 / t` knots. A missing or inapplicable JSON value is normally `null`; do
not assume that `0` and `null` mean the same thing.

## JSON structure

Each JSON file has three top-level fields:

| Field | Meaning |
| --- | --- |
| `rms` | Array containing one object per active certificate. |
| `Countries` | Lookup table of ORC country/authority codes and names. |
| `ScoringOptions` | Metadata describing standard and national scoring fields. |

Each `ScoringOptions` entry contains:

| Field | Meaning |
| --- | --- |
| `Fieldname` | Key used on each object in `rms`. |
| `Name` | Human-readable scoring option. |
| `Kind` | `TOD`, `TOT`, or `PCS`. |
| `CountryId` | Authority defining the option; `ORC` denotes a standard option. |
| `Families` | Certificate families for which the option applies. |

For example, use the standard options plus the relevant national authority:

```jq
.ScoringOptions[] | select(.CountryId == "ORC" or .CountryId == "EST")
```

### Certificate and boat identity

| JSON field | CSV field | Meaning |
| --- | --- | --- |
| `NatAuth` | `NAT` | National rating authority code. |
| `RefNo` | `ReferenceNo` | Unique ORC certificate reference. This is the identity used by the archive's deletion guard. |
| `CertNo` | `CERTN.` | Rating office's local certificate number, when supplied. |
| `BIN` | `FILE_ID` | ORC boat/file identifier. |
| `SailNo` | `SAILNUMB` | Sail number. It may be absent or may not include the authority prefix. |
| `YachtName` | `NAME` | Yacht name. |
| `Class` | `TYPE` | Yacht class, design, or model. |
| `Builder` | `BUILDER` | Builder. |
| `Designer` | `DESIGNER` | Designer. |
| `Age_Year` | `YEAR` | Boat age/series year. |
| `Club` | `CLUB` | Club or local affiliation, when supplied. |
| `C_Type` | `Family` | Certificate type; current regular feeds use `INTL` or `CLUB`. |
| `Family` | `C_Type` | Certificate family; this archive selects regular `ORC` records. |
| `Division` | `D` | IMS division: commonly `C` (Cruiser/Racer), `R` (Performance/Racer), or `S` (Sportboat). |
| `IssueDate` | `DD_MM_yyYY HH:MM:SS` | Issue timestamp. JSON uses an ISO 8601 UTC timestamp. |
| `metric` | — | Whether measurements use metric units; current archived records are `true`. |

Some sparse descriptive fields, such as `Address3`, may appear only for some
records. The legacy CSV also contains `OWNER`, `ADRS1`, and `ADRS2`; these are
often empty and have no guaranteed JSON counterpart.

The swapped `C_Type`/`Family` mapping above is intentional. In current ORC CSV
rows, `C_Type` contains values such as `ORC`, while `Family` contains `INTL` or
`CLUB`. Use the values rather than inferring semantics from those legacy header
names.

## Certificate-history schema

The generated `docs/certificates/<VPP year>/certificates.csv` files form the
canonical append-preserving index behind the GitHub Pages browser. One row
represents one observed `RefNo`, not one yacht. If a yacht receives four
certificates during a VPP year and each appears in a daily sample, all four rows
and certificate links remain in the history.

| Field | Meaning |
| --- | --- |
| `vpp_year` | VPP/rating year containing the observation. |
| `country`, `nat_auth` | Feed country and rating authority. |
| `ref_no` | Immutable ORC certificate reference and row identity. |
| `cert_no`, `bin` | Rating-office certificate number and ORC boat/file identifier. |
| `sail_no`, `yacht_name`, `class` | Searchable yacht identity and description as last observed for this certificate. |
| `certificate_type`, `family` | Values copied from JSON `C_Type` and `Family`. |
| `issue_date` | ORC-provided issue timestamp. |
| `first_seen_on` | First successful daily archive date on which this reference appeared. |
| `status` | `active` while present in the feed, otherwise `archived`. |
| `removed_on` | First successful archive date on which the reference was absent. |
| `certificate_url` | Stable ORC certificate-renderer URL derived from `ref_no`. |

Removal status is updated only after the deletion guard accepts the full run.
A country not advertised during a run is left unchanged rather than treating
all of its certificates as removed. ORC may serve printable HTML at a URL whose
path ends in `.pdf`; the archive stores the durable certificate link, not the
rendered document itself.

The generated `docs/performance/<year>/<country>.json` files are compact,
append-preserving inputs for the reusable Rating Performance Guide. They retain
certificate identity and only the allowance arrays required for target and
polar calculations. Invalid or incomplete polar matrices are omitted rather
than converted to zero. See [Rating Performance Guide](performance-guide.md)
for calculations, interpolation, units, and limitations.

Before merging the current feed, the updater reads added certificate records
from committed `data/**/*.json` patches. This backfills references observed
before the history CSV existed without reopening every complete historical
country file on each run. GitHub Actions uses a full clone so those revisions
are available.

### Hull and crew

| JSON field | CSV field | Unit | Meaning |
| --- | --- | --- | --- |
| `LOA` | `LOA` | m | Length overall. |
| `IMSL` | `IMSL` | m | IMS effective sailing length. |
| `CDL` | `CDL` | m | Class Division Length. |
| `MB` | `BMAX` | m | Maximum beam. |
| `Draft` | `DRAFT` | m | Draft. |
| `Dspl_Measurement` | `DSPL` | kg | Displacement in measurement trim. |
| `Dspl_Sailing` | `DSPS` | kg | Displacement in sailing trim. |
| `CrewWT` | `CREW` | kg | Rated crew weight. |
| `WSS` | `WSS` | m² | Wetted surface area. |
| `Stability_Index` | `INDEX` | — | ORC Stability Index, when available. |
| `Dynamic_Allowance` | `DA` | % | Rating credit for performance in unsteady conditions. |

### Sail areas

| JSON field | CSV field | Meaning |
| --- | --- | --- |
| `Area_Main` | `MAIN` | Rated maximum mainsail area. |
| `Area_Jib` | `GENOA` | Rated maximum jib/headsail area. |
| `Area_Sym` | `SYM` | Rated maximum symmetric spinnaker area. |
| `Area_Asym` | `ASYM` | Rated maximum asymmetric spinnaker area. |

All four sail-area values are in `m²`. A sail type not present in the rated
configuration is normally `null` in JSON.

CSV numeric fields are often rounded more aggressively than JSON, and some
JSON `null` values appear as `0.0` in CSV. The two formats describe the same
certificate feed but are not lossless representations of each other.

### Standard and legacy scoring fields

| JSON field | CSV field | Kind | Meaning |
| --- | --- | --- | --- |
| `GPH` | `GPH` | TOD | General Purpose Handicap reference value. |
| `APHD` | `APHTOD` | TOD | All-Purpose single-number rating. |
| `APHT` | `APHTOT` | TOT | All-Purpose single-number multiplier. |
| `ILCWA` | `ILCGA` | TOD | Windward/Leeward single-number rating. |
| `TMF_Inshore` | `TMF` | TOT | Windward/Leeward single-number multiplier. |
| `OSN` | `OSN` | TOD | Coastal/Long-Distance (legacy Offshore Single Number) rating. |
| `TMF_Offshore` | `TMF-OF` | TOT | Coastal/Long-Distance multiplier. |
| `Pred_Up_TOD` | `PREUPD` | TOD | Predominantly-upwind rating. |
| `Pred_Up_TOT` | `PREUPT` | TOT | Predominantly-upwind multiplier. |
| `Pred_Down_TOD` | `PREDND` | TOD | Predominantly-downwind rating. |
| `Pred_Down_TOT` | `PREDNT` | TOT | Predominantly-downwind multiplier. |

Triple-number fields use `Low`, `Medium`, and `High` wind ranges:

| JSON pattern | CSV pattern | Meaning |
| --- | --- | --- |
| `TND_Offshore_<range>` | `OTDLOW`, `OTDMED`, `OTDHIG` | Coastal/Long-Distance TOD. |
| `TN_Offshore_<range>` | `OTNLOW`, `OTNMED`, `OTNHIG` | Coastal/Long-Distance TOT. |
| `TND_Inshore_<range>` | `ITDLOW`, `ITDMED`, `ITDHIG` | Windward/Leeward TOD. |
| `TN_Inshore_<range>` | `ITNLOW`, `ITNMED`, `ITNHIG` | Windward/Leeward TOT. |

The CSV also exposes `DH_TOD` and `DH_TOT` for legacy double-handed scoring.

### Polar and selected-course allowances

`Allowances` is the JSON polar matrix. Array positions align with
`Allowances.WindSpeeds`, currently:

```text
[4, 6, 8, 10, 12, 14, 16, 20, 24] kt
```

The fixed true-wind angles are listed by `Allowances.WindAngles`, currently:

```text
[52, 60, 75, 90, 110, 120, 135, 150] degrees
```

| Allowances key | Unit | Meaning |
| --- | --- | --- |
| `Beat` | s/NM | Optimal upwind VMG time allowance. |
| `BeatAngle` | degrees | Optimal upwind true-wind angle. |
| `Run` | s/NM | Optimal downwind VMG time allowance. |
| `GybeAngle` | degrees | Optimal downwind true-wind angle. |
| `R52`, `R60`, `R75`, `R90`, `R110`, `R120`, `R135`, `R150` | s/NM | Time allowance at the named fixed true-wind angle. |
| `WL` | s/NM | Windward/Leeward selected-course allowance. |
| `CR` | s/NM | All-Purpose/Circular-Random selected-course allowance. |
| `OC` | s/NM | Ocean selected-course allowance. |
| `DW150`, `DW165`, `DW180` | s/NM | Fixed downwind-course allowances at the named angle. |

CSV flattens these arrays by appending true wind speed to the legacy prefix:

| CSV pattern | JSON source |
| --- | --- |
| `UA<tws>` | `Allowances.BeatAngle` |
| `DA<tws>` | `Allowances.GybeAngle` |
| `UP<tws>` | `Allowances.Beat` |
| `D<tws>` | `Allowances.Run` |
| `R<twa><tws>` | `Allowances.R<twa>` |
| `WL<tws>` | `Allowances.WL` |
| `CR<tws>` | `Allowances.CR` |
| `OC<tws>` | `Allowances.OC` |

For example, `R12014` is the `s/NM` allowance at 120° true wind angle and
14 kt true wind speed. The legacy CSV additionally contains `OL<tws>` and
`NSP<tws>` selected-course columns for 6–20 kt; `NSP` denotes a non-spinnaker
course. Their exact interpretation is not described by the JSON metadata.

### National scoring fields

JSON boat objects also contain many authority-specific keys, for example
`FIN_FinRating_TOD`, `GRE_NE_AP_TOT`, `IRL_WL6040_TOD`, and
`US_SFBay_H_TOT`. Do not hard-code a list: ORC can add or rename these options.
Resolve them through `ScoringOptions`:

```jq
.ScoringOptions[]
| select(.CountryId == "USA")
| {field: .Fieldname, name: .Name, kind: .Kind, families: .Families}
```

The `Kind` determines the unit and how a value is applied:

- `TOD`: seconds per nautical mile
- `TOT`: elapsed-time multiplier
- `PCS`: a polar/selected-course allowance

## CSV-only metadata

The current CSV schema contains 208 columns. In addition to the mappings above:

| CSV field | Meaning |
| --- | --- |
| `VPPYEAR` | VPP/rating year; this is also encoded by the archive directory. |
| `NAT`, `CERTN.`, `FILE_ID` | Authority, local certificate number, and ORC boat/file identifier. These are separate from `ReferenceNo`. |
| `OL<tws>` | Legacy selected-course time allowance. |
| `NSP<tws>` | Legacy non-spinnaker selected-course time allowance. |

CSV headers are retained exactly as supplied by ORC. Consumers should address
columns by header name rather than position and tolerate new columns.

## References

- [ORC rating-data acquisition API](https://data.orc.org/tools.php?c=pcs)
- [ORC scoring options and TOD/TOT formulas](https://orc.org/race-managment/scoring)
- [ORC International certificate field explanations](https://orc.org/organization/monohulls/orc-int-certificate)
- [Earlier community field notes](https://github.com/jieter/orc-data)
