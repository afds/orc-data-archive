# Performance Guide

The generated archive website includes a printable Performance Guide for
archived certificates with a complete public ORC allowance matrix. Open a
certificate year in the browser and choose **Performance guide**, or use a
shareable URL directly. If no valid public polar is archived for that
certificate, the guide shows an unavailable message at runtime.

```text
https://afds.github.io/orc-data-archive/performance/?year=2026&country=EST&ref=04340004VU1&windUnit=kt
```

The example above opens ADELE, EST 467.

## Cockpit reference

The first printable A4 landscape page prioritizes information that can be used
while sailing:

- optimum beat and run TWA, AWA, boat speed, and VMG for every published TWS;
- target boat speed at every published TWA, with derived AWA in each cell.

TWS labels can use knots or metres per second; target boat speed and VMG always
remain in knots. Separate Beat and Run tables appear first and show both angle
systems together. The target-speed table follows, using published TWS rows and
fixed TWA columns; each cell emphasizes boat speed and displays derived AWA as
a smaller secondary value.

The second page contains a mirrored speed polar. Apparent-wind angle is plotted
on the left, true-wind angle on the right, and radial distance is target boat
speed in knots. It includes all published TWS curves and marks optimum beat and
run endpoints.

## Calculations

The JSON `Allowances` object contains time allowances in seconds per nautical
mile for fixed true-wind angles, optimum beat and run, and a series of true wind
speeds.

At a fixed angle, predicted boat speed is:

```text
boat speed (kt) = 3600 / allowance (s/NM)
```

For optimum beat and run, `3600 / allowance` is VMG along the wind axis. Target
boat speed is recovered from VMG and the optimum angle. Apparent wind is then
derived from the TWS, TWA, and target boat-speed vectors using the relation
documented by ORC.

The sailor-facing guide displays only the certificate's published wind-speed
conditions. Apparent wind is recalculated for each published target without
rounding intermediate values.

See [ORC rating-data fields](data-fields.md#polar-and-selected-course-allowances)
for the archived arrays and their units.

## How to interpret the targets

AWA is the wind angle commonly felt by the crew and displayed by onboard
instruments. TWA describes the course relative to the underlying true wind.
Optimum beat and run angles maximize VMG toward a windward or leeward mark.

These are theoretical ORC VPP rating targets, not measurements of a particular
crew or day. Sea state, wind shear, sail condition, crew execution, and
instrument calibration can all change achievable performance. ORC predictions
use true wind referenced at 10 metres above the water.

## Why this is not an ORC Speed Guide

The feature is deliberately called a **Performance Guide**, not an ORC
Speed Guide. The public RMS feed does not contain enough input or intermediate
data to reproduce ORC's sail-specific product. In particular, it does not
provide:

- the complete individual sail inventory and all sail measurements;
- hull offsets and the complete hydrodynamic and stability model inputs;
- each candidate sail configuration before ORC selects the best result;
- heel, reef, flat, and other optimizer outputs;
- the canonical VPP implementation.

The archived allowance is an upper envelope of the configurations selected by
the VPP. Once only the winning value is published, the curves of the other sails
cannot be recovered uniquely. The archive therefore displays a general rating
polar without assigning curves to sails.

If an official Speed Guide is available for a certificate, it remains the
authoritative source for sail-specific curves and trim guidance.

## References

- [ORC Speed Guide sample](https://data.orc.org/public/samples/Speed_Guide_Sample.html)
- [ORC Speed Guide explanation](https://data.orc.org/public/samples/Speed_Guide_Explanation.pdf)
- [ORC VPP documentation 2026](https://orc.org/uploads/files/Rules-Regulations/2026/ORC-VPP-Documentation-2026.pdf)
- [ORC VPP designer software](https://orc.org/for-designers/orc-vpp)
