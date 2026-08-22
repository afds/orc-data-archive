import json
import csv
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from update_archive import (  # noqa: E402
    Change,
    Dataset,
    changed_sail_numbers,
    commit_message,
    csv_url,
    deletion_limit_exceeded,
    discover_datasets,
    normalize_csv_payload,
    normalize_payload,
    parse_csv_payload,
    removed_certificate_refs,
    update_archive,
)


INDEX_URL = "https://data.orc.org/public/WPub.dll/RMS?dox=1"


class UpdateArchiveTests(unittest.TestCase):
    def test_discovers_family_one_json_links_and_deduplicates(self):
        index = """
        <a href="/public/WPub.dll?action=DownRMS&amp;CountryId=EST&amp;ext=json&amp;Family=1&amp;VPPYear=2026">JSON</a>
        <a href="/public/WPub.dll?action=DownRMS&amp;CountryId=EST&amp;ext=json&amp;Family=1&amp;VPPYear=2026">JSON</a>
        <a href="/public/WPub.dll?action=DownRMS&amp;CountryId=EST&amp;ext=rms&amp;Family=1&amp;VPPYear=2026">RMS</a>
        <a href="/public/WPub.dll?action=DownRMS&amp;CountryId=EST&amp;ext=json&amp;Family=3&amp;VPPYear=2026">DH JSON</a>
        """
        datasets = discover_datasets(index, INDEX_URL)
        self.assertEqual(1, len(datasets))
        self.assertEqual((2026, "EST", 1), (datasets[0].year, datasets[0].country, datasets[0].family))

    def test_normalization_is_stable_and_sorts_boats(self):
        payload = {
            "rms": [
                {"YachtName": "Zulu", "SailNo": "EST 9", "RefNo": "B"},
                {"RefNo": "A", "SailNo": "EST 1", "YachtName": "Alpha"},
            ]
        }
        rendered = normalize_payload(payload).decode()
        self.assertLess(rendered.index('"SailNo":"EST 1"'), rendered.index('"SailNo":"EST 9"'))
        self.assertTrue(rendered.endswith("\n"))
        parsed = json.loads(rendered)
        self.assertCountEqual(payload["rms"], parsed["rms"])

    def test_csv_normalization_is_stable_and_sorts_boats(self):
        dataset = Dataset(2026, "EST", 1, "https://example.test?ext=json")
        raw = b'\xef\xbb\xbfNAT,SAILNUMB,NAME,FILE_ID,CERTN.\r\nEST,"EST 9",Zulu,B,2\r\nEST,"EST 1",Alpha,A,1\r\n'
        rows = parse_csv_payload(raw, dataset)

        rendered = normalize_csv_payload(rows)

        self.assertFalse(rendered.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\r\n", rendered)
        self.assertLess(rendered.index(b"EST 1"), rendered.index(b"EST 9"))

    def test_changed_sails_detects_add_modify_and_remove(self):
        old = {"rms": [{"SailNo": "EST 1", "GPH": 600}, {"SailNo": "EST 2"}]}
        new = {"rms": [{"SailNo": "EST 1", "GPH": 599}, {"SailNo": "EST 3"}]}
        self.assertEqual(("EST 1", "EST 2", "EST 3"), changed_sail_numbers(old, new))

    def test_removed_certificates_are_counted_by_reference(self):
        old = {"rms": [{"RefNo": "A"}, {"RefNo": "B"}, {"RefNo": "C"}]}
        new = {"rms": [{"RefNo": "A"}, {"RefNo": "C", "GPH": 599}]}
        self.assertEqual(("B",), removed_certificate_refs(old, new))

    def test_deletion_percentage_allows_boundary_and_rejects_above_it(self):
        self.assertFalse(deletion_limit_exceeded(1, 10, 10))
        self.assertTrue(deletion_limit_exceeded(2, 10, 10))

    def test_update_writes_year_country_and_keeps_unadvertised_files(self):
        index = b"""
        <a href="/public/WPub.dll?action=DownRMS&amp;CountryId=EST&amp;ext=json&amp;Family=1&amp;VPPYear=2026">JSON</a>
        """
        dataset_url = (
            "https://data.orc.org/public/WPub.dll?action=DownRMS&"
            "CountryId=EST&ext=json&Family=1&VPPYear=2026"
        )
        responses = {
            INDEX_URL: index,
            dataset_url: b'{"rms":[{"SailNo":"EST 467","RefNo":"NEW"}]}',
            csv_url(dataset_url): b'NAT,SAILNUMB,NAME,FILE_ID,CERTN.\r\nEST,"EST 467",Adele,NEW,1\r\n',
        }

        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory) / "data"
            retained = data_dir / "2025" / "EST.json"
            retained.parent.mkdir(parents=True)
            retained.write_text('{"rms":[]}\n')

            changes = update_archive(data_dir, fetcher=responses.__getitem__)

            self.assertEqual(1, len(changes))
            self.assertEqual(("EST 467",), changes[0].sail_numbers)
            self.assertTrue((data_dir / "2026" / "EST.json").exists())
            self.assertTrue((data_dir / "2026" / "EST.csv").exists())
            history = data_dir.parent / "docs" / "certificates" / "2026"
            self.assertTrue((history / "certificates.csv").exists())
            self.assertIn(
                'data-history-url="certificates.csv"',
                (history / "index.html").read_text(),
            )
            self.assertTrue(retained.exists())

    def test_update_backfills_certificates_from_git_observations(self):
        index = b"""
        <a href="/public/WPub.dll?action=DownRMS&amp;CountryId=LAT&amp;ext=json&amp;Family=1&amp;VPPYear=2026">JSON</a>
        """
        dataset_url = (
            "https://data.orc.org/public/WPub.dll?action=DownRMS&"
            "CountryId=LAT&ext=json&Family=1&VPPYear=2026"
        )
        responses = {
            INDEX_URL: index,
            dataset_url: b'{"rms":[{"RefNo":"NEW","SailNo":"LAT-790","YachtName":"Thunder"}]}',
            csv_url(dataset_url): b'NAT,SAILNUMB,NAME,FILE_ID,CERTN.\nLAT,LAT-790,Thunder,LAT-790,2\n',
        }
        git_observations = [
            (
                "2026-08-21",
                2026,
                "LAT",
                [{"RefNo": "OLD", "SailNo": "LAT-790", "YachtName": "Thunder"}],
            )
        ]

        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory) / "data"
            update_archive(
                data_dir,
                observed_on="2026-08-22",
                fetcher=responses.__getitem__,
                history_loader=lambda _: git_observations,
            )

            history_path = (
                data_dir.parent
                / "docs"
                / "certificates"
                / "2026"
                / "certificates.csv"
            )
            with history_path.open(encoding="utf-8", newline="") as source:
                rows = {row["ref_no"]: row for row in csv.DictReader(source)}

            self.assertEqual({"OLD", "NEW"}, set(rows))
            self.assertEqual("archived", rows["OLD"]["status"])
            self.assertEqual("2026-08-21", rows["OLD"]["first_seen_on"])
            self.assertEqual("active", rows["NEW"]["status"])

    def test_update_does_not_rewrite_unchanged_dataset(self):
        index = b"""
        <a href="/public/WPub.dll?action=DownRMS&amp;CountryId=EST&amp;ext=json&amp;Family=1&amp;VPPYear=2026">JSON</a>
        """
        dataset_url = (
            "https://data.orc.org/public/WPub.dll?action=DownRMS&"
            "CountryId=EST&ext=json&Family=1&VPPYear=2026"
        )
        responses = {
            INDEX_URL: index,
            dataset_url: b'{"rms":[{"RefNo":"SAME","SailNo":"EST 467"}]}',
            csv_url(dataset_url): b'NAT,SAILNUMB,NAME,FILE_ID,CERTN.\r\nEST,"EST 467",Adele,SAME,1\r\n',
        }

        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory) / "data"
            first_changes = update_archive(data_dir, fetcher=responses.__getitem__)
            json_path = data_dir / "2026" / "EST.json"
            csv_path = data_dir / "2026" / "EST.csv"
            first_json_stat = json_path.stat()
            first_csv_stat = csv_path.stat()
            history_path = data_dir.parent / "docs" / "certificates" / "2026" / "certificates.csv"
            first_history_stat = history_path.stat()

            second_changes = update_archive(data_dir, fetcher=responses.__getitem__)

            self.assertEqual(1, len(first_changes))
            self.assertEqual([], second_changes)
            self.assertEqual(first_json_stat.st_ino, json_path.stat().st_ino)
            self.assertEqual(first_csv_stat.st_ino, csv_path.stat().st_ino)
            self.assertEqual(first_history_stat.st_ino, history_path.stat().st_ino)

    def test_update_aborts_before_writing_when_deletion_limit_is_exceeded(self):
        index = b"""
        <a href="/public/WPub.dll?action=DownRMS&amp;CountryId=EST&amp;ext=json&amp;Family=1&amp;VPPYear=2026">JSON</a>
        """
        dataset_url = (
            "https://data.orc.org/public/WPub.dll?action=DownRMS&"
            "CountryId=EST&ext=json&Family=1&VPPYear=2026"
        )
        responses = {
            INDEX_URL: index,
            dataset_url: b'{"rms":[{"RefNo":"A"},{"RefNo":"B"},{"RefNo":"C"}]}',
            csv_url(dataset_url): b'NAT,SAILNUMB,NAME,FILE_ID,CERTN.\nEST,A,A,A,A\nEST,B,B,B,B\nEST,C,C,C,C\n',
        }

        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory) / "data"
            update_archive(data_dir, fetcher=responses.__getitem__)
            json_path = data_dir / "2026" / "EST.json"
            csv_path = data_dir / "2026" / "EST.csv"
            original_json = json_path.read_bytes()
            original_csv = csv_path.read_bytes()
            history_path = data_dir.parent / "docs" / "certificates" / "2026" / "certificates.csv"
            original_history = history_path.read_bytes()
            responses[dataset_url] = b'{"rms":[{"RefNo":"A"}]}'
            responses[csv_url(dataset_url)] = b'NAT,SAILNUMB,NAME,FILE_ID,CERTN.\nEST,A,A,A,A\n'

            with self.assertRaisesRegex(RuntimeError, r"2 of 3 \(66.7%\) removed"):
                update_archive(
                    data_dir,
                    max_deletion_percent=50,
                    fetcher=responses.__getitem__,
                )

            self.assertEqual(original_json, json_path.read_bytes())
            self.assertEqual(original_csv, csv_path.read_bytes())
            self.assertEqual(original_history, history_path.read_bytes())

    def test_commit_message_names_changed_sails(self):
        change = Change(
            dataset=Dataset(2026, "EST", 1, "https://example.test"),
            path=Path("data/2026/EST.json"),
            sail_numbers=("EST 379", "EST 467"),
        )
        message = commit_message([change])
        self.assertIn("EST 467", message.splitlines()[0])
        self.assertIn("2026/EST: EST 379, EST 467", message)


if __name__ == "__main__":
    unittest.main()
