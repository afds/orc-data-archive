"""Build append-preserving certificate history and a static browsing site."""

from __future__ import annotations

import csv
import html
import io
import json
import math
import urllib.parse
from collections.abc import Iterable
from pathlib import Path


HISTORY_FIELDS = (
    "vpp_year",
    "country",
    "nat_auth",
    "ref_no",
    "cert_no",
    "bin",
    "sail_no",
    "yacht_name",
    "class",
    "certificate_type",
    "family",
    "issue_date",
    "first_seen_on",
    "status",
    "removed_on",
    "certificate_url",
)
CERTIFICATE_URL = "https://data.orc.org/public/WPub.dll/CC/{ref_no}.pdf"
SAILOR_SERVICES_URL = "https://orc.org/sailors/sailor-services"
ACTIVE_CERTIFICATES_URL = "https://orc.org/sailors/active-certificates-database"


def certificate_url(ref_no: str) -> str:
    encoded = urllib.parse.quote(ref_no, safe="")
    return CERTIFICATE_URL.format(ref_no=encoded)


def _text(value: object) -> str:
    return "" if value is None else " ".join(str(value).split())


def _finite_numbers(value: object, *, positive: bool = False) -> list | None:
    if not isinstance(value, list) or not value:
        return None
    numbers = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return None
        if not math.isfinite(item) or positive and item <= 0:
            return None
        numbers.append(item)
    return numbers


def _strictly_increasing(values: list) -> bool:
    return all(left < right for left, right in zip(values, values[1:]))


def _angle_key(angle: int | float) -> str:
    return str(angle).removesuffix(".0")


def extract_performance_record(
    year: int,
    country: str,
    boat: dict,
    status: str,
) -> dict | None:
    """Return the compact validated polar fields needed by the guide."""
    ref_no = _text(boat.get("RefNo"))
    allowances = boat.get("Allowances")
    if not ref_no or not isinstance(allowances, dict):
        return None

    wind_speeds = _finite_numbers(allowances.get("WindSpeeds"), positive=True)
    wind_angles = _finite_numbers(allowances.get("WindAngles"), positive=True)
    if (
        wind_speeds is None
        or wind_angles is None
        or not _strictly_increasing(wind_speeds)
        or not _strictly_increasing(wind_angles)
        or wind_angles[-1] >= 180
    ):
        return None

    series = {}
    for source, target, positive in (
        ("Beat", "beat", True),
        ("BeatAngle", "beat_angle", False),
        ("Run", "run", True),
        ("GybeAngle", "gybe_angle", False),
    ):
        values = _finite_numbers(allowances.get(source), positive=positive)
        if values is None or len(values) != len(wind_speeds):
            return None
        if not positive and any(angle < 0 or angle > 180 for angle in values):
            return None
        series[target] = values
    if any(angle >= 90 for angle in series["beat_angle"]):
        return None
    if any(angle <= 90 for angle in series["gybe_angle"]):
        return None

    fixed = {}
    for angle in wind_angles:
        key = _angle_key(angle)
        values = _finite_numbers(allowances.get(f"R{key}"), positive=True)
        if values is None or len(values) != len(wind_speeds):
            return None
        fixed[key] = values

    return {
        "ref_no": ref_no,
        "sail_no": _text(boat.get("SailNo")),
        "yacht_name": _text(boat.get("YachtName")),
        "class": _text(boat.get("Class")),
        "issue_date": _text(boat.get("IssueDate")),
        "status": status,
        "vpp_year": year,
        "country": country,
        "certificate_url": certificate_url(ref_no),
        "allowances": {
            "wind_speeds": wind_speeds,
            "wind_angles": wind_angles,
            **series,
            "fixed": fixed,
        },
    }


def _active_record(
    year: int,
    country: str,
    boat: dict,
    observed_on: str,
    previous: dict[str, str] | None,
) -> dict[str, str]:
    ref_no = _text(boat.get("RefNo"))
    if not ref_no:
        raise ValueError(f"{year}/{country} contains a certificate without RefNo")
    first_seen_on = observed_on
    if previous and previous.get("first_seen_on"):
        first_seen_on = min(previous["first_seen_on"], observed_on)
    return {
        "vpp_year": str(year),
        "country": country,
        "nat_auth": _text(boat.get("NatAuth")),
        "ref_no": ref_no,
        "cert_no": _text(boat.get("CertNo")),
        "bin": _text(boat.get("BIN")),
        "sail_no": _text(boat.get("SailNo")),
        "yacht_name": _text(boat.get("YachtName")),
        "class": _text(boat.get("Class")),
        "certificate_type": _text(boat.get("C_Type")),
        "family": _text(boat.get("Family")),
        "issue_date": _text(boat.get("IssueDate")),
        "first_seen_on": first_seen_on,
        "status": "active",
        "removed_on": "",
        "certificate_url": certificate_url(ref_no),
    }


def _load_history(path: Path, year: int) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        missing = set(HISTORY_FIELDS) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path} is missing history fields: {sorted(missing)}")
        records = {}
        for row in reader:
            ref_no = row["ref_no"]
            if not ref_no:
                raise ValueError(f"{path} contains an empty ref_no")
            if ref_no in records:
                raise ValueError(f"{path} contains duplicate ref_no {ref_no}")
            if row["vpp_year"] != str(year):
                raise ValueError(f"{path} contains VPP year {row['vpp_year']}")
            record = {field: row.get(field, "") for field in HISTORY_FIELDS}
            if record["status"] == "removed":
                record["status"] = "archived"
            if record["status"] not in {"active", "archived"}:
                raise ValueError(f"{path} contains invalid status {record['status']}")
            records[ref_no] = record
    return records


def _render_csv(records: dict[str, dict[str, str]]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=HISTORY_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(
        sorted(
            records.values(),
            key=lambda row: (
                row["country"].casefold(),
                row["sail_no"].casefold(),
                row["yacht_name"].casefold(),
                row["ref_no"].casefold(),
            ),
        )
    )
    return output.getvalue().encode("utf-8")


def _load_performance(path: Path, year: int, country: str) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} contains malformed performance JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        raise ValueError(f"{path} has an invalid performance record envelope")
    records = {}
    for record in payload["records"]:
        if not isinstance(record, dict) or not _text(record.get("ref_no")):
            raise ValueError(f"{path} contains an invalid performance record")
        if record.get("vpp_year") != year or record.get("country") != country:
            raise ValueError(f"{path} contains a performance record for another dataset")
        ref_no = record["ref_no"]
        if ref_no in records:
            raise ValueError(f"{path} contains duplicate performance ref {ref_no}")
        records[ref_no] = record
    return records


def _render_performance_json(records: dict[str, dict]) -> bytes:
    ordered = sorted(
        records.values(),
        key=lambda record: (
            record["sail_no"].casefold(),
            record["yacht_name"].casefold(),
            record["ref_no"].casefold(),
        ),
    )
    rendered = json.dumps(
        {"records": ordered},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"{rendered}\n".encode()


def _render_performance_page() -> bytes:
    body = """<header class="site-header screen-only">
  <a class="brand" href="../">ORC certificate archive</a>
</header>
<main class="performance-main">
  <section class="performance-controls screen-only" id="performance-controls" aria-label="Reference controls">
    <fieldset id="wind-unit"><legend>Wind</legend>
      <label><input type="radio" name="wind-unit" value="kt" checked> knots</label>
      <label><input type="radio" name="wind-unit" value="ms"> m/s</label>
    </fieldset>
    <button class="print-button" id="print-guide" type="button">Print / Save PDF</button>
  </section>

  <section class="guide-error screen-only" id="guide-error" role="alert" hidden>
    <h2>Performance guide unavailable</h2>
    <p id="guide-error-message"></p>
    <a id="guide-error-link" href="../">Return to the certificate archive</a>
  </section>

  <div id="performance-guide" hidden>
    <section class="performance-sheet cockpit-sheet" id="cockpit-sheet" aria-labelledby="guide-title">
      <header class="guide-header">
        <div><p class="eyebrow">Performance Guide</p><h2 id="guide-title"><span id="yacht-name"></span> <small id="sail-number"></small></h2></div>
        <div class="guide-meta"><span id="certificate-ref"></span><span id="issue-date"></span></div>
      </header>
      <section class="performance-table-section optimum-section" aria-labelledby="vmg-heading"><h3 id="vmg-heading">Best VMG targets</h3><div class="optimum-tables">
        <div class="table-wrap"><table class="vmg-table"><caption>Beat</caption><thead><tr><th scope="col">TWS</th><th scope="col">TWA</th><th scope="col">AWA</th><th scope="col">Speed</th><th scope="col">VMG</th></tr></thead><tbody id="beat-targets"></tbody></table></div>
        <div class="table-wrap"><table class="vmg-table"><caption>Run</caption><thead><tr><th scope="col">TWS</th><th scope="col">TWA</th><th scope="col">AWA</th><th scope="col">Speed</th><th scope="col">VMG</th></tr></thead><tbody id="run-targets"></tbody></table></div>
      </div></section>
      <section class="performance-table-section" aria-labelledby="speed-heading"><h3 id="speed-heading">Target boat speed</h3><div class="table-wrap"><table class="speed-table"><thead id="speed-head"></thead><tbody id="speed-body"></tbody></table></div></section>
      <footer class="sheet-note">Theoretical ORC VPP rating targets. Actual performance varies with sea state, wind shear, crew execution, and instrument calibration.</footer>
    </section>

    <section class="performance-sheet polar-sheet" id="polar-sheet" aria-labelledby="polar-heading">
      <header class="guide-header"><div><p class="eyebrow">Performance Guide</p><h2 id="polar-heading"><span id="polar-yacht-name"></span> <small id="polar-sail-number"></small></h2></div><div class="guide-meta"><span id="polar-certificate-ref"></span><span id="polar-issue-date"></span></div></header>
      <div class="polar-legend" id="polar-legend" aria-label="True wind speed curves"></div>
      <div class="polar-chart" id="polar-chart"><div class="polar-tooltip" id="polar-tooltip" role="tooltip" hidden aria-live="polite"></div></div>
    </section>
  </div>
  <noscript><p class="guide-error">JavaScript is required to calculate and display this performance guide.</p></noscript>
</main>"""
    return _page(
        "Performance Guide",
        body,
        "../",
        module_script="../assets/performance.js",
    )


def _page(
    title: str,
    body: str,
    asset_prefix: str,
    with_script: bool = False,
    module_script: str | None = None,
) -> bytes:
    script = (
        f'<script src="{asset_prefix}assets/site.js" defer></script>'
        if with_script
        else ""
    )
    if module_script is not None:
        script = f'<script type="module" src="{module_script}"></script>'
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="History of public ORC rating certificates">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="{asset_prefix}assets/site.css">
  {script}
</head>
<body>
{body}
</body>
</html>
"""
    return document.encode("utf-8")


def _year_navigation(years: list[int], current: int) -> str:
    links = []
    for year in sorted(years, reverse=True):
        current_attr = ' aria-current="page"' if year == current else ""
        links.append(f'<a href="../{year}/"{current_attr}>{year}</a>')
    return "".join(links)


def _official_sources_notice() -> str:
    return f"""<aside class="official-notice" aria-label="Official ORC certificate sources">
    <strong>Unofficial archive</strong>
    <p>This independent site is not an official ORC service. For official certificates, use
      <a href="{SAILOR_SERVICES_URL}">ORC Sailor Services</a> or the
      <a href="{ACTIVE_CERTIFICATES_URL}">ORC Active Certificates Database</a>.
    </p>
  </aside>"""


def _render_year_page(
    year: int,
    years: list[int],
    records: dict[str, dict[str, str]],
) -> bytes:
    active = sum(record["status"] == "active" for record in records.values())
    archived = len(records) - active
    body = f"""<header class="site-header">
  <a class="brand" href="../../">ORC certificate archive</a>
  <nav class="year-nav" aria-label="VPP years">{_year_navigation(years, year)}</nav>
</header>
<main>
  <section class="year-intro">
    <div>
      <h1>{year} certificates</h1>
      <p>Certificates observed in the public ORC rating feed, retained after removal.</p>
    </div>
    <dl class="summary">
      <div><dt>Active</dt><dd id="active-count">{active:,}</dd></div>
      <div><dt>Archived</dt><dd id="archived-count">{archived:,}</dd></div>
      <div><dt>Total</dt><dd id="total-count">{len(records):,}</dd></div>
    </dl>
  </section>
  {_official_sources_notice()}
  <section class="browser" aria-labelledby="browser-heading"
           data-history-url="certificates.csv">
    <div class="browser-heading">
      <div>
        <h2 id="browser-heading">Yachts</h2>
        <p><span id="visible-count">Loading…</span></p>
      </div>
      <div class="filters">
        <label>Search
          <input id="search" type="search" placeholder="Yacht, sail number, country or ORC ref">
        </label>
        <label>Status
          <select id="status-filter">
            <option value="all">All certificates</option>
            <option value="active">Active</option>
            <option value="archived">Archived</option>
          </select>
        </label>
        <label>Country
          <select id="country-filter">
            <option value="all">All countries</option>
          </select>
        </label>
        <label>Certificate type
          <select id="type-filter">
            <option value="all">All types</option>
            <option value="INTL">International</option>
            <option value="CLUB">Club</option>
          </select>
        </label>
      </div>
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Yacht</th><th>Sail no.</th><th>Country</th><th>Type</th><th>Issued</th><th>Status</th><th>ORC certificate</th></tr></thead>
        <tbody></tbody>
      </table>
      <p class="empty-state" id="empty-state">Loading certificate history…</p>
    </div>
    <button class="load-more" id="load-more" type="button" hidden>Show more</button>
  </section>
  <footer><a href="certificates.csv">Download {year} certificate history CSV</a>
    <span>Independent archive; certificate pages are served by ORC.</span></footer>
</main>"""
    return _page(f"{year} ORC certificates", body, "../../", with_script=True)


def _render_index(
    histories: dict[int, dict[str, dict[str, str]]],
) -> bytes:
    year_links = []
    for year in sorted(histories, reverse=True):
        records = histories[year].values()
        total = len(histories[year])
        active = sum(record["status"] == "active" for record in records)
        year_links.append(
            f"""<a class="year-row" href="certificates/{year}/">
  <span class="year">{year}</span>
  <span><strong>{total:,}</strong> observed certificates</span>
  <span><strong>{active:,}</strong> currently active</span>
  <span class="arrow" aria-hidden="true">→</span>
</a>"""
        )
    body = f"""<header class="site-header">
  <span class="brand">ORC certificate archive</span>
  <a class="repo-link" href="https://github.com/afds/orc-data-archive">GitHub repository</a>
</header>
<main>
  <section class="home-intro">
    <h1>Find an ORC certificate</h1>
    <p>Browse yachts by VPP year and open the certificate retained by its ORC reference.</p>
  </section>
  {_official_sources_notice()}
  <section class="years" aria-labelledby="years-heading">
    <div class="section-title"><h2 id="years-heading">VPP years</h2><p>Updated daily from ORC's public active-certificate feed.</p></div>
    <div class="year-list">{''.join(year_links)}</div>
  </section>
  <footer><a href="https://github.com/afds/orc-data-archive/blob/main/docs/data-fields.md">Data field reference</a>
    <span>Historical observations may omit certificate revisions between daily snapshots.</span></footer>
</main>"""
    return _page("ORC certificate archive", body, "")


def build_history_site(
    site_dir: Path,
    observations: Iterable[tuple[int, str, list[dict]]],
    observed_on: str,
    historical_observations: Iterable[
        tuple[str, int, str, list[dict]]
    ] = (),
) -> dict[Path, bytes]:
    """Return all history/site files that should exist after this observation."""
    observations = list(observations)
    historical_observations = list(historical_observations)
    history_root = site_dir / "certificates"
    histories: dict[int, dict[str, dict[str, str]]] = {}
    for path in history_root.glob("*/certificates.csv"):
        try:
            year = int(path.parent.name)
        except ValueError:
            continue
        histories[year] = _load_history(path, year)

    for historical_date, year, country, boats in historical_observations:
        history = histories.setdefault(year, {})
        for boat in boats:
            ref_no = _text(boat.get("RefNo"))
            if not ref_no:
                raise ValueError(
                    f"historical {year}/{country} contains a certificate without RefNo"
                )
            previous = history.get(ref_no)
            if previous:
                first_seen = previous.get("first_seen_on")
                if not first_seen or historical_date < first_seen:
                    previous["first_seen_on"] = historical_date
            else:
                history[ref_no] = _active_record(
                    year, country, boat, historical_date, None
                )

    observed_countries: dict[int, set[str]] = {}
    active_by_year: dict[int, dict[str, tuple[str, dict]]] = {}
    for year, country, boats in observations:
        observed_countries.setdefault(year, set()).add(country)
        active = active_by_year.setdefault(year, {})
        for boat in boats:
            ref_no = _text(boat.get("RefNo"))
            if not ref_no:
                raise ValueError(f"{year}/{country} contains a certificate without RefNo")
            if ref_no in active:
                raise ValueError(f"duplicate active certificate reference {ref_no}")
            active[ref_no] = (country, boat)

    for year, active in active_by_year.items():
        history = histories.setdefault(year, {})
        for ref_no, (country, boat) in active.items():
            history[ref_no] = _active_record(
                year, country, boat, observed_on, history.get(ref_no)
            )
        checked_countries = observed_countries[year]
        for ref_no, record in history.items():
            if (
                record["country"] in checked_countries
                and ref_no not in active
                and record["status"] == "active"
            ):
                record["status"] = "archived"
                record["removed_on"] = observed_on

    performance_root = site_dir / "performance"
    performance: dict[tuple[int, str], dict[str, dict]] = {}
    for path in performance_root.glob("*/*.json"):
        try:
            year = int(path.parent.name)
        except ValueError:
            continue
        country = path.stem.upper()
        performance[(year, country)] = _load_performance(path, year, country)

    for _, year, country, boats in historical_observations:
        records = performance.setdefault((year, country), {})
        for boat in boats:
            compact = extract_performance_record(year, country, boat, "archived")
            if compact is not None:
                records.setdefault(compact["ref_no"], compact)

    for year, country, boats in observations:
        records = performance.setdefault((year, country), {})
        for boat in boats:
            compact = extract_performance_record(year, country, boat, "active")
            if compact is not None:
                records[compact["ref_no"]] = compact

    for (year, country), records in performance.items():
        history = histories.get(year, {})
        for ref_no, compact in records.items():
            historical = history.get(ref_no)
            if historical is not None:
                compact["status"] = historical["status"]

    years = sorted(histories)
    planned = {
        site_dir / "index.html": _render_index(histories),
        performance_root / "index.html": _render_performance_page(),
    }
    for year in years:
        year_dir = history_root / str(year)
        planned[year_dir / "certificates.csv"] = _render_csv(histories[year])
        planned[year_dir / "index.html"] = _render_year_page(
            year, years, histories[year]
        )
    for (year, country), records in sorted(performance.items()):
        if records:
            planned[
                performance_root / str(year) / f"{country}.json"
            ] = _render_performance_json(records)
    return planned
