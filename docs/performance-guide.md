# Performance guide feasibility

This note records the likely direction for a future performance view in the
generated website. It is a design note, not a commitment to implement the
feature.

## Proposed direction

Generate a general, non-sail-specific polar for each archived certificate from
the public RMS allowance data. The feature should be described as a
**Performance Guide** or **Rating Polar**, not as an ORC Speed Guide.

A future certificate view could include:

- a true-wind-angle polar across the available true wind speeds
- optimum beat and run angles and speeds
- a numeric target table with boat speed and VMG
- derived apparent wind angle and apparent wind speed
- certificate identity and maximum rated sail areas
- a printable layout and downloadable tabular data
- shareable URL state containing at least VPP year, country, and ORC reference

An SVG chart with a semantic HTML table fallback would keep the output crisp in
print, usable on mobile, and accessible without requiring a charting framework.
A reusable page backed by compact generated country/year data is preferable to
generating thousands of nearly identical HTML files.

## What the archive can calculate

The JSON `Allowances` object contains time allowances in seconds per nautical
mile for fixed true-wind angles, optimum beat and run, and a series of true wind
speeds. The corresponding predicted boat speed is:

```text
boat speed (kt) = 3600 / allowance (s/NM)
```

VMG can be calculated from boat speed and true wind angle. Apparent wind angle
and speed can be derived from the true-wind vector and predicted boat speed.
See [ORC rating-data fields](data-fields.md#polar-and-selected-course-allowances)
for the archived arrays and their units.

These values describe the best rated performance selected by the ORC VPP at
each published condition. They are suitable for a general polar, subject to the
normal limitation that this is theoretical rating data rather than measured
on-water performance.

## Why exact per-sail curves cannot be reconstructed

ORC's public VPP documentation explains the overall calculation and publishes
many aerodynamic equations and coefficient tables. At each wind condition the
VPP evaluates eligible sail configurations, solves aerodynamic and hydrodynamic
equilibrium, optimizes controls such as reef and flat, and retains the fastest
result.

The public RMS feed does not contain enough input or intermediate data to repeat
that process. In particular, it does not provide:

- the complete individual sail inventory and all sail measurements
- hull offsets and the complete hydrodynamic and stability model inputs
- the result of each candidate sail configuration before ORC selects the best
- heel, reef, flat, and other intermediate optimizer outputs
- the canonical VPP implementation

The archived allowance is therefore an upper envelope of candidate sail
configurations. Once only the winning value is published, the curves of the
other sails cannot be uniquely recovered: many different sets of per-sail
curves could produce the same envelope.

Implementing the formulas in the public documentation would be a new VPP
implementation rather than a simple inversion of the RMS data. It would also
require measurement inputs that this archive does not possess and extensive
validation against official results.

## Future support for official Speed Guides

If an official Speed Guide is available for a certificate, its machine-readable
tables could be archived and presented as an additional, explicitly sourced
view. This would preserve genuine per-sail curves without inferring them from
the general RMS polar. Availability, redistribution rights, and stable download
access would need to be established before automating collection.

## References

- [ORC Speed Guide sample](https://data.orc.org/public/samples/Speed_Guide_Sample.html)
- [ORC Speed Guide explanation](https://data.orc.org/public/samples/Speed_Guide_Explanation.pdf)
- [ORC VPP documentation 2026](https://orc.org/uploads/files/Rules-Regulations/2026/ORC-VPP-Documentation-2026.pdf)
- [ORC VPP designer software](https://orc.org/for-designers/orc-vpp)
