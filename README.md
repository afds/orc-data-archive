# ORC data archive

This repository takes daily snapshots of the public Offshore Racing Congress
(ORC) rating-data JSON and CSV feeds. Git history preserves each observed revision of
the active certificate data.

The updater discovers available regular ORC datasets (`Family=1`) from the
[ORC RMS index](https://data.orc.org/public/WPub.dll/RMS?dox=1), downloads each
advertised JSON and CSV feeds, validates them, and writes deterministic snapshots to:

```text
data/<VPP year>/<rating-office country>.{json,csv}
```

For example, Estonian certificates using the 2026 VPP are stored in
[`data/2026/EST.json`](data/2026/EST.json) and
[`data/2026/EST.csv`](data/2026/EST.csv). Country/year files are updated in
place, so all of their observed versions remain available through Git history.
Files from years no longer advertised by ORC are retained.

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
across every dataset. It aborts the entire run if more than 25 certificates have
disappeared, guarding against truncated or faulty upstream responses. The limit
is configurable with `--max-deletions` and is explicit in the workflow.

## Reading history

```bash
git log -- data/2026/EST.json
git log -p -- data/2026/EST.json
git show <commit>:data/2026/EST.json
```

The archive is a daily sampling of ORC's active-data feed, not an ORC-issued
certificate ledger. If a boat receives multiple replacement certificates
between two workflow runs, intermediate revisions may not be observed.

## Data format

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
