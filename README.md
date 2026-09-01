# ORC data archive

This repository takes daily snapshots of the public Offshore Racing Congress
(ORC) rating-data JSON and CSV feeds. Git history preserves each observed
revision of the active certificate data.

The updater discovers regular ORC datasets (`Family=1`) from the
[ORC RMS index](https://data.orc.org/public/WPub.dll/RMS?dox=1), validates them,
and writes deterministic snapshots to:

```text
data/<VPP year>/<rating-office country>.{json,csv}
```

Country/year files are updated in place, and files no longer advertised by ORC
are retained.

The generated [certificate browser](https://bitblit.eu/orc-data-archive/)
supports search and filtering and links each reference to its public ORC
certificate. Its history is keyed by immutable ORC reference, preserving
removed and replacement certificates as separate records.

## Performance Guide

Certificate rows link to a printable Performance Guide. When public polar data
is available, it shows beat and run targets, a target boat-speed table with
derived AWA, and an interactive mirrored AWA/TWA polar. See the
[Performance Guide](docs/performance-guide.md) for its calculation model and
public-data limitations.

## Updating

Run the updater with Python 3.11 or newer:

```bash
python scripts/update_archive.py
```

The [daily workflow](.github/workflows/archive.yml) runs at 04:17 UTC and can
also be started manually. It skips unchanged datasets and aborts before writing
if a country/year dataset unexpectedly loses more than 50% of its certificate
references.

## Reading history

```bash
git log -- data/2026/EST.json
git log -p -- data/2026/EST.json
git show <commit>:data/2026/EST.json
```

The archive is a daily sample of ORC's active-data feed, not an ORC-issued
certificate ledger. Revisions that appear and disappear between successful
runs may not be observed.

## Data format

The archive preserves the original payloads semantically. See
[ORC rating-data fields](docs/data-fields.md) for the JSON and CSV structures,
units, polar arrays, and national scoring options.

ORC owns and operates the upstream service. This repository is an independent
archive and is not affiliated with or endorsed by ORC.
