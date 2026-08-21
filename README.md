# ORC data archive

This repository takes weekly snapshots of the public Offshore Racing Congress
(ORC) rating-data JSON feeds. Git history preserves each observed revision of
the active certificate data.

The updater discovers available regular ORC datasets (`Family=1`) from the
[ORC RMS index](https://data.orc.org/public/WPub.dll/RMS?dox=1), downloads each
advertised JSON feed, validates it, and writes a deterministic snapshot to:

```text
data/<VPP year>/<rating-office country>.json
```

For example, Estonian certificates using the 2026 VPP are stored in
[`data/2026/EST.json`](data/2026/EST.json). A country/year file is updated in
place, so all of its observed versions remain available through Git history.
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

The [weekly workflow](.github/workflows/archive.yml) runs every Monday and can
also be started manually. It commits directly only when normalized data has
changed. Its commit subject and body identify affected sail numbers.

## Reading history

```bash
git log -- data/2026/EST.json
git log -p -- data/2026/EST.json
git show <commit>:data/2026/EST.json
```

The archive is a weekly sampling of ORC's active-data feed, not an ORC-issued
certificate ledger. If a boat receives multiple replacement certificates
between two workflow runs, intermediate revisions may not be observed.

## Data format

The original payload is preserved semantically, including every boat field.
For stable, reviewable diffs, boats and object keys are sorted and each boat is
written on one line. The top-level shape remains:

```json
{
  "rms": [
    {"RefNo":"...","SailNo":"..."}
  ]
}
```

ORC owns and operates the upstream service. This repository is an independent
archive and is not affiliated with or endorsed by ORC.
