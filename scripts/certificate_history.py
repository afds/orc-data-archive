"""Build append-preserving certificate history and a static browsing site."""

from __future__ import annotations

import csv
import html
import io
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


def certificate_url(ref_no: str) -> str:
    encoded = urllib.parse.quote(ref_no, safe="")
    return CERTIFICATE_URL.format(ref_no=encoded)


def _text(value: object) -> str:
    return "" if value is None else " ".join(str(value).split())


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
            records[ref_no] = {field: row.get(field, "") for field in HISTORY_FIELDS}
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


def _page(title: str, body: str, asset_prefix: str, with_script: bool = False) -> bytes:
    script = (
        f'<script src="{asset_prefix}assets/site.js" defer></script>'
        if with_script
        else ""
    )
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


def _render_year_page(
    year: int,
    years: list[int],
    records: dict[str, dict[str, str]],
) -> bytes:
    active = sum(record["status"] == "active" for record in records.values())
    removed = len(records) - active
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
      <div><dt>Archived</dt><dd id="removed-count">{removed:,}</dd></div>
      <div><dt>Total</dt><dd id="total-count">{len(records):,}</dd></div>
    </dl>
  </section>
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
            <option value="removed">Removed</option>
          </select>
        </label>
        <label>Country
          <select id="country-filter">
            <option value="all">All countries</option>
          </select>
        </label>
      </div>
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Yacht</th><th>Sail no.</th><th>Country</th><th>Issued</th><th>Status</th><th>ORC certificate</th></tr></thead>
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
                record["status"] = "removed"
                record["removed_on"] = observed_on

    years = sorted(histories)
    planned = {site_dir / "index.html": _render_index(histories)}
    for year in years:
        year_dir = history_root / str(year)
        planned[year_dir / "certificates.csv"] = _render_csv(histories[year])
        planned[year_dir / "index.html"] = _render_year_page(
            year, years, histories[year]
        )
    return planned
