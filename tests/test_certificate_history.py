import csv
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from certificate_history import build_history_site, certificate_url  # noqa: E402


def write_plan(plan: dict[Path, bytes]) -> None:
    for path, content in plan.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


class CertificateHistoryTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
