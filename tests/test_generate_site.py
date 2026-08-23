import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

try:
    from generate_site import generate_site  # noqa: E402
except ImportError:
    generate_site = lambda *args, **kwargs: []


class GenerateSiteTests(unittest.TestCase):
    def test_regenerates_site_deterministically_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_dir = root / "data"
            site_dir = root / "docs"
            country_path = data_dir / "2026" / "EST.json"
            country_path.parent.mkdir(parents=True)
            country_path.write_text(
                json.dumps(
                    {
                        "rms": [
                            {
                                "RefNo": "A",
                                "SailNo": "EST 467",
                                "YachtName": "ADELE",
                                "Allowances": {
                                    "WindSpeeds": [8, 10],
                                    "WindAngles": [52],
                                    "Beat": [895.5, 793.2],
                                    "BeatAngle": [41.6, 40],
                                    "Run": [797.6, 672],
                                    "GybeAngle": [149.8, 152.5],
                                    "R52": [601, 548.3],
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            first = generate_site(
                data_dir,
                site_dir,
                "2026-08-23",
                history_loader=lambda _: [],
            )
            snapshot = {
                path.relative_to(site_dir): path.read_bytes()
                for path in site_dir.rglob("*")
                if path.is_file()
            }
            second = generate_site(
                data_dir,
                site_dir,
                "2026-08-23",
                history_loader=lambda _: [],
            )

            self.assertGreater(len(first), 0)
            self.assertEqual([], second)
            self.assertEqual(
                snapshot,
                {
                    path.relative_to(site_dir): path.read_bytes()
                    for path in site_dir.rglob("*")
                    if path.is_file()
                },
            )
            self.assertTrue((site_dir / "performance" / "2026" / "EST.json").exists())


if __name__ == "__main__":
    unittest.main()
