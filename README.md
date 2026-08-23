# ORC data archive

This repository takes daily snapshots of the public Offshore Racing Congress
(ORC) rating-data JSON and CSV feeds. Git history preserves each observed
revision of the active certificate data.

The updater discovers available regular ORC datasets (`Family=1`) from the
[ORC RMS index](https://data.orc.org/public/WPub.dll/RMS?dox=1), downloads each
advertised JSON and CSV feeds, validates them, and writes deterministic
snapshots to:

```text
data/<VPP year>/<rating-office country>.{json,csv}
```

For example, Estonian certificates using the 2026 VPP are stored in
[`data/2026/EST.json`](data/2026/EST.json) and
[`data/2026/EST.csv`](data/2026/EST.csv). Country/year files are updated in
place, so all of their observed versions remain available through Git history.
Files from years no longer advertised by ORC are retained.

The generated [certificate browser](https://afds.github.io/orc-data-archive/)
groups yachts by VPP year, supports country, status, and Club/International
certificate-type filters, and links each ORC reference to its public certificate
page. Its canonical history is stored in
`docs/certificates/<year>/certificates.csv`; certificates remain in that file
after disappearing from the active feed and receive an observed removal date.
History is keyed by immutable ORC reference, so every observed replacement
certificate for the same yacht remains a separate searchable row and link. The
updater also backfills certificate records from committed JSON revisions,
including snapshots created before the browser was introduced.

Browser filters are shareable. Search, country, and non-default status values
are preserved in the URL, for example:

```text
https://bitblit.eu/orc-data-archive/certificates/2026/?search=LAT-790&country=LAT&status=active&type=club
```

## Rating Performance Guide

Certificate rows link to a reusable Rating Performance Guide. It provides
complete beat and run targets when public polar data is available, a
boat-speed/AWA table, and a mirrored AWA/TWA polar. The two-sheet A4
landscape layout can be printed directly or saved as PDF.

Guide state is shareable by VPP year, country, ORC reference, and wind unit.
For example, ADELE (EST 467) uses:

```text
https://afds.github.io/orc-data-archive/performance/?year=2026&country=EST&ref=04340004VU1&windUnit=kt
```

Only TWS switches between knots and metres per second; target boat speed and
VMG remain in knots. See the
[Rating Performance Guide](docs/performance-guide.md) documentation for the
calculation model, sailor-facing guidance, and public-data limitations.

## Updating

Run the updater with Python 3.11 or newer; it has no third-party dependencies:

```bash
python scripts/update_archive.py
```

To preview the commit message generated from changed sail numbers:

```bash
python scripts/update_archive.py --summary-file /tmp/orc-commit-message.txt
cat /tmp/orc-commit-message.txt
```

The [daily workflow](.github/workflows/archive.yml) runs at 04:17 UTC and can
also be started manually. The updater does not rewrite byte-identical normalized
datasets, and the workflow creates and pushes a commit only when the staged data
diff is non-empty. Its commit subject and body identify affected sail numbers.

Before writing any files, the updater compares certificate reference numbers
within each country/year dataset. It aborts the entire run if any dataset loses
more than 10% of its previously archived certificates, guarding against
truncated or faulty upstream responses while accounting for different fleet
sizes. The limit is configurable with `--max-deletion-percent` and is explicit
in the workflow.

## Reading history

```bash
git log -- data/2026/EST.json
git log -p -- data/2026/EST.json
git show <commit>:data/2026/EST.json
```

The archive is a daily sampling of ORC's active-data feed, not an ORC-issued
certificate ledger. If a boat receives multiple replacement certificates
between two workflow runs, intermediate revisions may not be observed. Every
revision present during at least one successful daily run is retained.

## Data format

See [ORC rating-data fields](docs/data-fields.md) for the JSON structure, CSV
column mappings, units, polar arrays, and national scoring options.

See [Rating Performance Guide](docs/performance-guide.md) for the printable
non-sail-specific polar view, the values derived from the archive, and why the
public feed cannot reproduce ORC's per-sail Speed Guide.

The original payloads are preserved semantically, including every boat field.
For stable, reviewable diffs, JSON boats and object keys are sorted and each
boat is written on one line. The top-level JSON shape remains:

```json
{
  "rms": [
    {"RefNo":"...","SailNo":"..."}
  ]
}
```

CSV files are stored as UTF-8 without a BOM, use LF line endings, retain all
columns, and sort boat rows deterministically.

ORC owns and operates the upstream service. This repository is an independent
archive and is not affiliated with or endorsed by ORC.
