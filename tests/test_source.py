"""A published file says where its data comes from and under what licence, and when OpenStreetMap's data was current."""
import json
import os
import tempfile
import unittest
from unittest import mock

import build
from golf import fetch
from golf.clean import ATTRIBUTION, SOURCE, country_file


class Notice(unittest.TestCase):
    def test_the_attribution_names_the_licence_and_links_it(self):
        self.assertIn("© OpenStreetMap contributors", ATTRIBUTION)
        self.assertIn("https://opendatacommons.org/licenses/odbl/1-0/", ATTRIBUTION)
        self.assertIn("https://www.openstreetmap.org/copyright", ATTRIBUTION)

    def test_a_country_file_has_its_source_and_when_the_data_was_current(self):
        data = country_file("SE", "Sweden", [], {}, "2026-11-09T02:10:00Z", "2026-11-09T01:58:00Z")
        self.assertEqual(data["source"], dict(SOURCE, osmBase="2026-11-09T01:58:00Z"))
        self.assertEqual(data["source"]["licenceUrl"], "https://opendatacommons.org/licenses/odbl/1-0/")
        self.assertNotIn("osmBase", country_file("SE", "Sweden", [], {}, "x")["source"])

    def test_the_oldest_of_the_four_answers_gives_when_the_data_was_current(self):
        with tempfile.TemporaryDirectory() as folder:
            for name, stamp in zip(("outlines", "relations", "holes", "greens"),
                                   ("2026-11-09T01:58:00Z", "2026-11-09T01:50:00Z", "2026-11-09T02:01:00Z", "2026-11-09T01:59:00Z")):
                with open(os.path.join(folder, name + ".json"), "w") as f:
                    json.dump({"osm3s": {"timestamp_osm_base": stamp}, "elements": []}, f)
            self.assertEqual(build.osm_base(folder), "2026-11-09T01:50:00Z")
            os.remove(os.path.join(folder, "greens.json"))
            self.assertIsNone(build.osm_base(folder))   # one missing: not guessed

    def test_a_fetch_keeps_the_time_overpass_says_the_data_is_from(self):
        answer = json.dumps({"osm3s": {"timestamp_osm_base": "2026-11-09T01:58:00Z", "copyright": "x"}, "elements": [{"id": 1}]}).encode()
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(fetch, "post", return_value=(200, answer)):
            fetch.fetch("SE", folder)
            with open(os.path.join(folder, "outlines.json")) as f:
                saved = json.load(f)
        self.assertEqual(saved["osm3s"], {"timestamp_osm_base": "2026-11-09T01:58:00Z"})
        self.assertEqual(saved["elements"], [{"id": 1}])


if __name__ == "__main__":
    unittest.main()
