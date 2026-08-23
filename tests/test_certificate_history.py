import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import certificate_history  # noqa: E402
from certificate_history import build_history_site, certificate_url  # noqa: E402


extract_performance_record = getattr(
    certificate_history,
    "extract_performance_record",
    lambda year, country, boat, status: None,
)


def polar_boat(ref_no: str = "A") -> dict:
    return {
        "RefNo": ref_no,
        "SailNo": "EST 467",
        "YachtName": "ADELE",
        "Class": "First 34.7",
        "IssueDate": "2026-07-31T09:26:27Z",
        "Allowances": {
            "WindSpeeds": [8, 10],
            "WindAngles": [52, 60],
            "Beat": [895.5, 793.2],
            "BeatAngle": [41.6, 40.0],
            "Run": [797.6, 672.0],
            "GybeAngle": [149.8, 152.5],
            "R52": [601.0, 548.3],
            "R60": [576.7, 532.9],
        },
    }


def write_plan(plan: dict[Path, bytes]) -> None:
    for path, content in plan.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


class CertificateHistoryTests(unittest.TestCase):
    def test_extracts_only_valid_compact_performance_fields(self):
        boat = polar_boat()
        boat["GPH"] = 600.1

        record = extract_performance_record(2026, "EST", boat, "active")

        self.assertIsNotNone(record)
        self.assertEqual("A", record["ref_no"])
        self.assertEqual([8, 10], record["allowances"]["wind_speeds"])
        self.assertEqual({"52", "60"}, set(record["allowances"]["fixed"]))
        self.assertNotIn("GPH", record)

    def test_rejects_incomplete_or_non_finite_polar(self):
        incomplete = polar_boat("SHORT")
        incomplete["Allowances"]["R60"] = [576.7]
        non_finite = polar_boat("INFINITE")
        non_finite["Allowances"]["Beat"][0] = float("inf")
        impossible_angles = polar_boat("ANGLES")
        impossible_angles["Allowances"]["BeatAngle"][0] = 95
        impossible_angles["Allowances"]["GybeAngle"][0] = 85

        self.assertIsNone(
            extract_performance_record(2026, "EST", incomplete, "active")
        )
        self.assertIsNone(
            extract_performance_record(2026, "EST", non_finite, "active")
        )
        self.assertIsNone(
            extract_performance_record(2026, "EST", impossible_angles, "active")
        )

    def test_generates_and_preserves_compact_performance_records(self):
        with tempfile.TemporaryDirectory() as directory:
            site_dir = Path(directory) / "docs"
            write_plan(
                build_history_site(
                    site_dir,
                    [(2026, "EST", [polar_boat()])],
                    "2026-08-22",
                )
            )

            performance_path = site_dir / "performance" / "2026" / "EST.json"
            payload = json.loads(performance_path.read_text())
            self.assertEqual(["A"], [record["ref_no"] for record in payload["records"]])
            self.assertEqual("active", payload["records"][0]["status"])
            self.assertTrue((site_dir / "performance" / "index.html").exists())

            write_plan(
                build_history_site(
                    site_dir,
                    [(2026, "EST", [])],
                    "2026-08-23",
                )
            )

            payload = json.loads(performance_path.read_text())
            self.assertEqual(["A"], [record["ref_no"] for record in payload["records"]])
            self.assertEqual("archived", payload["records"][0]["status"])

    def test_backfills_historical_performance_record(self):
        with tempfile.TemporaryDirectory() as directory:
            site_dir = Path(directory) / "docs"
            write_plan(
                build_history_site(
                    site_dir,
                    [(2026, "EST", [])],
                    "2026-08-23",
                    historical_observations=[
                        ("2026-08-21", 2026, "EST", [polar_boat("OLD")])
                    ],
                )
            )

            payload = json.loads(
                (site_dir / "performance" / "2026" / "EST.json").read_text()
            )
            self.assertEqual("OLD", payload["records"][0]["ref_no"])
            self.assertEqual("archived", payload["records"][0]["status"])

    def test_certificate_history_does_not_persist_derived_performance_urls(self):
        with tempfile.TemporaryDirectory() as directory:
            site_dir = Path(directory) / "docs"
            invalid = {"RefNo": "NO-POLAR", "YachtName": "No polar"}
            write_plan(
                build_history_site(
                    site_dir,
                    [(2026, "EST", [polar_boat(), invalid])],
                    "2026-08-22",
                )
            )

            with (
                site_dir / "certificates" / "2026" / "certificates.csv"
            ).open(encoding="utf-8", newline="") as source:
                reader = csv.DictReader(source)
                rows = {row["ref_no"]: row for row in reader}

            self.assertNotIn("performance_url", reader.fieldnames)
            self.assertEqual({"A", "NO-POLAR"}, set(rows))

    def test_generates_performance_page_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            site_dir = Path(directory) / "docs"
            write_plan(
                build_history_site(
                    site_dir,
                    [(2026, "EST", [polar_boat()])],
                    "2026-08-22",
                )
            )

            page = (site_dir / "performance" / "index.html").read_text()
            self.assertIn(
                'type="module" src="../assets/performance.js"',
                page,
            )
            self.assertIn('id="performance-controls"', page)
            self.assertIn('id="guide-error" role="alert"', page)
            self.assertIn('id="cockpit-sheet"', page)
            self.assertIn('id="certificate-ref"', page)
            self.assertIn('id="polar-certificate-ref"', page)
            self.assertNotIn('id="vpp-year"', page)
            self.assertIn('id="polar-sheet"', page)
            self.assertIn("Configure reference", page)
            self.assertIn('id="matrix-heading">Target boat speed</h3>', page)
            self.assertNotIn('id="tws-input"', page)
            self.assertNotIn('id="beat-card"', page)
            self.assertNotIn('id="run-card"', page)
            self.assertNotIn('id="wind-presets"', page)
            self.assertNotIn('id="control-status"', page)
            self.assertNotIn("Published TWS", page)
            self.assertIn('id="polar-yacht-name"', page)
            self.assertIn('id="polar-sail-number"', page)
            self.assertNotIn('id="polar-boat-name"', page)
            self.assertEqual(1, page.count("<table"))
            self.assertIn('id="performance-head"', page)
            self.assertIn('id="performance-body"', page)
            self.assertNotIn('id="beat-targets"', page)
            self.assertNotIn('id="run-targets"', page)
            self.assertNotIn('id="target-matrix"', page)

    def test_certificate_url_uses_orc_reference(self):
        self.assertEqual(
            "https://data.orc.org/public/WPub.dll/CC/04340004VU1.pdf",
            certificate_url("04340004VU1"),
        )

    def test_history_retains_removed_certificates_by_year(self):
        with tempfile.TemporaryDirectory() as directory:
            site_dir = Path(directory) / "docs"
            initial = [
                (
                    2026,
                    "EST",
                    [
                        {
                            "RefNo": "A",
                            "IssueDate": "2026-04-01T10:00:00Z",
                            "SailNo": "EST 1",
                            "YachtName": "Alpha",
                        },
                        {
                            "RefNo": "B",
                            "IssueDate": "2026-05-01T10:00:00Z",
                            "SailNo": "EST 2",
                            "YachtName": "Bravo",
                        },
                    ],
                )
            ]
            write_plan(build_history_site(site_dir, initial, "2026-08-21"))
            write_plan(
                build_history_site(
                    site_dir,
                    [(2026, "EST", [initial[0][2][0]])],
                    "2026-08-22",
                )
            )

            history_path = site_dir / "certificates" / "2026" / "certificates.csv"
            with history_path.open(encoding="utf-8", newline="") as source:
                rows = {row["ref_no"]: row for row in csv.DictReader(source)}

            self.assertEqual("active", rows["A"]["status"])
            self.assertEqual("archived", rows["B"]["status"])
            self.assertEqual("2026-08-22", rows["B"]["removed_on"])
            self.assertEqual("2026-05-01T10:00:00Z", rows["B"]["issue_date"])
            self.assertTrue(rows["B"]["certificate_url"].endswith("/B.pdf"))

    def test_replacement_certificates_for_one_yacht_are_all_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            site_dir = Path(directory) / "docs"
            for day, ref_no in enumerate(("REF-1", "REF-2", "REF-3", "REF-4"), 1):
                write_plan(
                    build_history_site(
                        site_dir,
                        [
                            (
                                2026,
                                "EST",
                                [
                                    {
                                        "RefNo": ref_no,
                                        "BIN": "0434000",
                                        "IssueDate": f"2026-06-{day:02d}T10:00:00Z",
                                        "SailNo": "EST 123",
                                        "YachtName": "Adele",
                                    }
                                ],
                            )
                        ],
                        f"2026-06-{day:02d}",
                    )
                )

            history_path = site_dir / "certificates" / "2026" / "certificates.csv"
            with history_path.open(encoding="utf-8", newline="") as source:
                rows = list(csv.DictReader(source))

            self.assertEqual(4, len(rows))
            self.assertEqual({"REF-1", "REF-2", "REF-3", "REF-4"}, {row["ref_no"] for row in rows})
            self.assertEqual(1, sum(row["status"] == "active" for row in rows))
            self.assertEqual(3, sum(row["status"] == "archived" for row in rows))

            page = (site_dir / "certificates" / "2026" / "index.html").read_text()
            self.assertIn('data-history-url="certificates.csv"', page)
            self.assertIn('id="type-filter"', page)
            self.assertIn('<th>Type</th>', page)

    def test_unadvertised_country_is_not_marked_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            site_dir = Path(directory) / "docs"
            write_plan(
                build_history_site(
                    site_dir,
                    [(2025, "AUS", [{"RefNo": "OLD", "YachtName": "Old boat"}])],
                    "2026-08-21",
                )
            )
            write_plan(
                build_history_site(
                    site_dir,
                    [(2026, "EST", [{"RefNo": "NEW", "YachtName": "New boat"}])],
                    "2026-08-22",
                )
            )

            path = site_dir / "certificates" / "2025" / "certificates.csv"
            with path.open(encoding="utf-8", newline="") as source:
                row = next(csv.DictReader(source))
            self.assertEqual("active", row["status"])
            self.assertEqual("", row["removed_on"])

    def test_generated_pages_link_to_official_orc_certificate_services(self):
        with tempfile.TemporaryDirectory() as directory:
            site_dir = Path(directory) / "docs"
            write_plan(
                build_history_site(
                    site_dir,
                    [(2026, "EST", [{"RefNo": "A", "YachtName": "Adele"}])],
                    "2026-08-22",
                )
            )

            for path in (
                site_dir / "index.html",
                site_dir / "certificates" / "2026" / "index.html",
            ):
                page = path.read_text()
                self.assertIn("Unofficial archive", page)
                self.assertIn("https://orc.org/sailors/sailor-services", page)
                self.assertIn(
                    "https://orc.org/sailors/active-certificates-database",
                    page,
                )

    def test_mobile_layout_rules_do_not_apply_while_printing(self):
        stylesheet = (
            Path(__file__).resolve().parents[1] / "docs" / "assets" / "site.css"
        ).read_text(encoding="utf-8")

        self.assertIn("@media screen and (max-width: 760px)", stylesheet)
        self.assertIn(
            ".performance-sheet tbody th { text-transform: none; }",
            stylesheet,
        )


if __name__ == "__main__":
    unittest.main()
