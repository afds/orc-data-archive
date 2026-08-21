#!/usr/bin/env python3
"""Archive the JSON datasets advertised by ORC's public RMS index."""

from __future__ import annotations

import argparse
import html.parser
import json
import os
import random
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


INDEX_URL = "https://data.orc.org/public/WPub.dll/RMS?dox=1"
USER_AGENT = "orc-data-archive/1.0 (+https://github.com/afds/orc-data-archive)"


@dataclass(frozen=True, order=True)
class Dataset:
    year: int
    country: str
    family: int
    url: str


@dataclass(frozen=True)
class Change:
    dataset: Dataset
    path: Path
    sail_numbers: tuple[str, ...]


class RMSIndexParser(html.parser.HTMLParser):
    def __init__(self, base_url: str, family: int) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.family = family
        self.datasets: set[Dataset] = set()

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if not href:
            return

        url = urllib.parse.urljoin(self.base_url, href)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        if _one(query, "action").lower() != "downrms":
            return
        if _one(query, "ext").lower() != "json":
            return

        try:
            family = int(_one(query, "Family"))
            year = int(_one(query, "VPPYear"))
        except (TypeError, ValueError):
            return
        country = _one(query, "CountryId").upper()
        if family != self.family or not country or year < 2000:
            return

        self.datasets.add(
            Dataset(year=year, country=country, family=family, url=url)
        )


def _one(query: dict[str, list[str]], name: str) -> str:
    values = query.get(name)
    return values[0] if values else ""


def discover_datasets(index_html: str, base_url: str, family: int = 1) -> list[Dataset]:
    parser = RMSIndexParser(base_url, family)
    parser.feed(index_html)
    return sorted(parser.datasets)


def fetch(url: str, attempts: int = 4, timeout: int = 60) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json,text/html;q=0.9,*/*;q=0.1", "User-Agent": USER_AGENT},
    )
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError):
            if attempt == attempts:
                raise
            time.sleep((2 ** (attempt - 1)) + random.random())
    raise AssertionError("unreachable")


def parse_payload(raw: bytes, dataset: Dataset) -> dict:
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{dataset.url} did not return valid JSON") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("rms"), list):
        raise ValueError(f"{dataset.url} has no top-level rms list")
    if not all(isinstance(boat, dict) for boat in payload["rms"]):
        raise ValueError(f"{dataset.url} contains a non-object boat record")
    return payload


def boat_sort_key(boat: dict) -> tuple[str, ...]:
    return tuple(
        str(boat.get(field) or "").casefold()
        for field in ("SailNo", "YachtName", "RefNo", "CertNo", "BIN")
    )


def normalize_payload(payload: dict) -> bytes:
    normalized = dict(payload)
    normalized["rms"] = sorted(payload["rms"], key=boat_sort_key)
    lines = ["{", '  "rms": [']
    boats = normalized.pop("rms")
    for index, boat in enumerate(boats):
        suffix = "," if index + 1 < len(boats) else ""
        encoded = json.dumps(
            boat, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        lines.append(f"    {encoded}{suffix}")
    lines.append("  ]")
    for key in sorted(normalized):
        encoded_key = json.dumps(key, ensure_ascii=False)
        encoded_value = json.dumps(
            normalized[key], ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        lines[-1] += ","
        lines.append(f"  {encoded_key}: {encoded_value}")
    lines.append("}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def sail_label(boat: dict) -> str:
    for field in ("SailNo", "YachtName", "RefNo", "CertNo", "BIN"):
        value = str(boat.get(field) or "").strip()
        if value:
            return " ".join(value.split())
    return "<unknown boat>"


def _boats_by_label(payload: dict | None) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    if payload is None:
        return {}
    for boat in payload["rms"]:
        signature = json.dumps(
            boat, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        grouped[sail_label(boat)].append(signature)
    return {label: tuple(sorted(values)) for label, values in grouped.items()}


def changed_sail_numbers(old: dict | None, new: dict) -> tuple[str, ...]:
    before = _boats_by_label(old)
    after = _boats_by_label(new)
    labels = set(before) | set(after)
    return tuple(sorted((label for label in labels if before.get(label) != after.get(label)), key=str.casefold))


def read_existing(path: Path, dataset: Dataset) -> dict | None:
    if not path.exists():
        return None
    return parse_payload(path.read_bytes(), dataset)


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(content)
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def update_archive(
    data_dir: Path,
    family: int = 1,
    workers: int = 4,
    fetcher: Callable[[str], bytes] = fetch,
    index_url: str = INDEX_URL,
) -> list[Change]:
    index_html = fetcher(index_url).decode("utf-8-sig")
    datasets = discover_datasets(index_html, index_url, family)
    if not datasets:
        raise RuntimeError(f"no Family={family} JSON datasets found at {index_url}")

    downloaded: dict[Dataset, dict] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(fetcher, dataset.url): dataset for dataset in datasets}
        for future in as_completed(futures):
            dataset = futures[future]
            downloaded[dataset] = parse_payload(future.result(), dataset)

    changes: list[Change] = []
    for dataset in datasets:
        payload = downloaded[dataset]
        path = data_dir / str(dataset.year) / f"{dataset.country}.json"
        content = normalize_payload(payload)
        if path.exists() and path.read_bytes() == content:
            continue
        old = read_existing(path, dataset)
        atomic_write(path, content)
        changes.append(
            Change(
                dataset=dataset,
                path=path,
                sail_numbers=changed_sail_numbers(old, payload),
            )
        )
    return changes


def commit_message(changes: Iterable[Change]) -> str:
    changes = list(changes)
    all_sails = sorted(
        {sail for change in changes for sail in change.sail_numbers}, key=str.casefold
    )
    shown = all_sails[:8]
    subject = "Update ORC data"
    if shown:
        subject += ": " + ", ".join(shown)
        if len(all_sails) > len(shown):
            subject += f" (+{len(all_sails) - len(shown)} more)"

    body = []
    for change in sorted(changes, key=lambda item: item.dataset):
        sails = list(change.sail_numbers)
        displayed = sails[:100]
        details = ", ".join(displayed) if displayed else "normalized dataset changed"
        if len(sails) > len(displayed):
            details += f" (+{len(sails) - len(displayed)} more)"
        body.append(f"{change.dataset.year}/{change.dataset.country}: {details}")
    return subject + ("\n\n" + "\n".join(body) if body else "") + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--family", type=int, default=1)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--summary-file", type=Path)
    parser.add_argument("--index-url", default=INDEX_URL)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    changes = update_archive(
        data_dir=args.data_dir,
        family=args.family,
        workers=args.workers,
        index_url=args.index_url,
    )
    message = commit_message(changes)
    if args.summary_file:
        args.summary_file.parent.mkdir(parents=True, exist_ok=True)
        args.summary_file.write_text(message, encoding="utf-8")
    print(message, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
