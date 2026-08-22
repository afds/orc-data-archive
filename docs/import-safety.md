# Import safety review

Status: deferred proposals; none of the safeguards in this document are
implemented merely by documenting them.

This note records a system-level review of the ORC archive importer and
potential hardening work to consider before substantially expanding the
archive. The current archive was internally consistent at the time of review:
42 JSON/CSV dataset pairs contained 8,177 certificates, with no missing or
duplicate references and exact agreement between the JSON and CSV reference
sets.

## System map

The daily import passes through these stages:

```text
GitHub Actions schedule
  -> discover country/year feeds from the ORC RMS index
  -> download every JSON and CSV dataset
  -> parse and normalize the responses
  -> compare removals with the previous snapshots
  -> build the append-preserving certificate history and static website
  -> atomically replace changed files in the worktree
  -> commit and push only when the staged data or site changed
```

The principal components are:

- `.github/workflows/archive.yml`: schedules the import and commits accepted
  changes
- `scripts/update_archive.py`: discovers, downloads, validates, normalizes, and
  writes datasets
- `scripts/certificate_history.py`: maintains certificate history and generates
  the website
- `data/<year>/<country>.{json,csv}`: canonical active-feed snapshots
- `docs/certificates/<year>/certificates.csv`: append-preserving observed
  certificate history

## Existing safeguards

The current design already has useful fail-closed behaviour:

- all advertised datasets must download and parse before writes begin
- a removal-policy violation in one dataset aborts the entire run
- countries absent from the index are retained rather than treated as removed
- each changed file is replaced atomically
- a failed importer step prevents the workflow from committing or pushing
- overlapping scheduled imports are prevented by workflow concurrency
- deterministic normalization avoids commits for byte-identical data
- the workflow exits without a commit when nothing changed
- normal pushes are used; the workflow never force-pushes

These protections primarily cover network failures, malformed top-level
responses, excessive reference removal, interrupted file replacement, and
no-op runs. They do not yet establish strong source, schema, or cross-format
integrity.

## Priority 0: source and path confinement

Dataset discovery currently trusts links in the RMS index more than necessary.
The discovered URL host and path are not constrained, and any non-empty
`CountryId` is accepted before the country value is used in an output path.

Future hardening should:

- require the expected HTTPS origin and `/public/WPub.dll` endpoint
- restrict country identifiers to the expected three uppercase ASCII letters
- reject unreasonable VPP years
- resolve every destination and verify it remains below the configured data
  directory
- reject duplicate country/year datasets whose URLs disagree

Source validation should happen during discovery, before any URL is fetched or
destination path is constructed.

## Priority 0: certificate identity and schema validation

The JSON parser currently establishes only that `rms` is an array of objects.
Identity validation should be explicit because deletion detection, history, and
certificate links all depend on `RefNo`.

Every candidate JSON dataset should require:

- one non-empty string `RefNo` per certificate
- unique references within the country/year dataset
- the expected `Family` value
- a known certificate type such as `CLUB` or `INTL`
- parseable issue timestamps when supplied
- expected collection and scalar types for fields used by the importer

Sparse descriptive and future unknown fields should continue to be preserved.
Validation should distinguish required archive invariants from optional ORC
fields so harmless schema additions do not block imports.

## Priority 0: JSON and CSV agreement

JSON and CSV are fetched independently. They may represent different upstream
moments, or one response may be stale or incomplete. Both formats currently
parse independently without being compared.

Before accepting a country/year pair, the importer should require:

- the identity headers needed for comparison
- equal certificate row counts
- identical non-empty reference sets
- unique references in both formats
- agreement on a small set of stable identity fields where practical

On disagreement, the pair may be retried together with backoff in case a
certificate was issued between the two requests. Persistent disagreement
should abort the entire run without writing.

## Priority 1: broader anomaly policy

The current relative deletion guard catches only disappearing references and
uses a strict greater-than comparison, so exactly 10% removal is accepted when
the configured limit is 10%.

A future policy could combine hard integrity rules with anomaly quarantine:

- treat removal at or above the configured percentage as anomalous
- detect unusually large additions, with an explicit bootstrap policy for new
  country/year datasets
- detect mass modification of records whose references remain unchanged
- quarantine unexpectedly empty newly advertised datasets
- cap individual response size, aggregate download size, and certificate count
- detect a large change in the set of country/year datasets advertised by ORC

Hard schema and identity violations should abort outright. Statistical changes
that might be legitimate should be quarantined for review rather than silently
accepted or permanently rejected.

## Priority 1: candidate and quarantine workflow

For stronger whole-run isolation, the importer could construct a complete
candidate tree outside the worktree:

1. Fetch and normalize all responses.
2. Validate source, schema, identity, and JSON/CSV agreement.
3. Generate the candidate certificate history and website.
4. Report additions, removals, modifications, counts, and hashes.
5. Apply the complete candidate to the worktree only after every check passes.

When a statistical anomaly needs manual acceptance, approval should identify
the exact candidate content hash. A broad option that disables safeguards would
make it too easy to approve different data from the data that was reviewed.

## Priority 1: archive retention and workflow security

Git history is the archive, so repository history itself should receive
explicit protection:

- prevent force pushes and deletion of the default branch while retaining
  normal workflow pushes
- pin third-party GitHub Actions to immutable commit hashes
- run unit tests and a complete candidate validator before the commit step
- periodically mirror the repository or create a recoverable `git bundle`
  outside the primary repository

The scheduled workflow should remain unable to push after any failed validation
or test step.

## Priority 2: observability and long-term maintenance

Potential follow-up improvements include:

- publish per-dataset counts and change percentages in the Actions step summary
- upload a candidate manifest and diagnostics artifact after rejected imports
- notify maintainers when scheduled imports repeatedly fail
- distinguish an actively checked dataset from a country that disappeared from
  the index and has therefore become stale
- stop replaying the complete Git log on every daily run now that the historical
  backfill is materialized in the canonical history CSV files
- add regression tests for unsafe index values, duplicate or missing references,
  JSON/CSV disagreement, empty bootstrap datasets, and post-validation no-write
  guarantees

## Suggested implementation order

If this work is undertaken, the smallest high-value sequence is:

1. Constrain index URLs, country identifiers, years, and destination paths.
2. Add strict reference validation and JSON/CSV identity comparison.
3. Add regression tests for every rejected-input case.
4. Add candidate metrics and tune anomaly thresholds from observed changes.
5. Protect repository history and add an independent backup.
6. Introduce quarantine approval only if legitimate exceptional imports make it
   necessary.

This ordering closes deterministic integrity gaps before adding heuristics or a
more elaborate approval process.
