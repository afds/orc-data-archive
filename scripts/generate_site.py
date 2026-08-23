#!/usr/bin/env python3
"""Regenerate the static site from committed archive JSON without networking."""

from __future__ import annotations

import argparse
import datetime
import json
from collections.abc import Callable, Iterable
from pathlib import Path

from certificate_history import build_history_site
from update_archive import HistoryObservation, atomic_write, load_git_observations


def generate_site(
    data_dir: Path,
    site_dir: Path,
    observed_on: str,
    history_loader: Callable[[Path], Iterable[HistoryObservation]] = load_git_observations,
) -> list[Path]:
    """Regenerate deterministic site files from committed JSON without network access."""
    datetime.date.fromisoformat(observed_on)
    observations = []
    for path in sorted(data_dir.glob("*/*.json")):
        try:
            year = int(path.parent.name)
        except ValueError:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path} contains malformed JSON") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("rms"), list):
            raise ValueError(f"{path} must contain an rms array")
        observations.append((year, path.stem.upper(), payload["rms"]))

    if not observations:
        raise ValueError(f"no country/year JSON datasets found under {data_dir}")

    planned = build_history_site(
        site_dir,
        observations,
        observed_on,
        historical_observations=history_loader(data_dir.parent),
    )
    changed = []
    for path, content in sorted(planned.items()):
        if path.exists() and path.read_bytes() == content:
            continue
        atomic_write(path, content)
        changed.append(path)
    return changed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--site-dir", type=Path, default=Path("docs"))
    parser.add_argument("--observed-on", required=True, help="UTC date, YYYY-MM-DD")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    changed = generate_site(
        data_dir=args.data_dir,
        site_dir=args.site_dir,
        observed_on=args.observed_on,
    )
    for path in changed:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
