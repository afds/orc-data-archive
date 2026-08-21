import json
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
    discover_datasets,
    normalize_payload,
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

    def test_changed_sails_detects_add_modify_and_remove(self):
        old = {"rms": [{"SailNo": "EST 1", "GPH": 600}, {"SailNo": "EST 2"}]}
        new = {"rms": [{"SailNo": "EST 1", "GPH": 599}, {"SailNo": "EST 3"}]}
        self.assertEqual(("EST 1", "EST 2", "EST 3"), changed_sail_numbers(old, new))

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
            self.assertTrue(retained.exists())

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
        }

        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory) / "data"
            first_changes = update_archive(data_dir, fetcher=responses.__getitem__)
            path = data_dir / "2026" / "EST.json"
            first_stat = path.stat()

            second_changes = update_archive(data_dir, fetcher=responses.__getitem__)

            self.assertEqual(1, len(first_changes))
            self.assertEqual([], second_changes)
            self.assertEqual(first_stat.st_ino, path.stat().st_ino)

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
