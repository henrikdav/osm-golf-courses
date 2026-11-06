"""The report of what the data has: each club's level and what it lacks, the totals, and the history."""
import json
import os
import tempfile
import unittest

from golf.report import add_to_history, club_row, page, report


def course(key, holes=9, complete=True):
    return {"key": key, "name": key, "complete": complete, "notes": [], "holes": [{"n": i + 1, "path": []} for i in range(holes)]}


def club(cid, courses=(), combos=None, **more):
    out = {"id": cid, "name": "Club " + cid, "courses": list(courses)}
    if combos:
        out["combos"] = combos
    out.update(more)
    return out


class Levels(unittest.TestCase):
    def test_each_level_and_what_it_lacks(self):
        self.assertEqual((club_row(club("a"))["level"], club_row(club("a"))["lacks"]), (0, "holes on the map"))
        self.assertEqual(club_row(club("b", [course("main", 9, complete=False)]))["level"], 1)
        row = club_row(club("c", [course("main", 18)]))
        self.assertEqual((row["level"], row["lacks"]), (2, ""))

    def test_a_row_says_nothing_of_golf_data(self):
        row = club_row(club("d", [course("main", 18)], clubFile={"what": "x"}))
        self.assertEqual(set(row), {"id", "name", "level", "lacks", "courses", "complete", "combos", "notes"})


class Report(unittest.TestCase):
    def test_totals_and_the_best_clubs_first(self):
        rep = report("SE", [club("a"), club("d", [course("main", 18)])], "2026-11-03T02:00:00Z")
        self.assertEqual(rep["totals"]["name only"], 1)
        self.assertEqual(rep["totals"]["a whole course"], 1)
        self.assertEqual(rep["clubs"][0]["id"], "d")

    def test_the_history_keeps_one_entry_a_day(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "reports", "SE.json")
            add_to_history(path, report("SE", [club("a")], "2026-11-03T02:00:00Z"))
            add_to_history(path, report("SE", [club("a"), club("b")], "2026-11-03T05:00:00Z"))
            history = add_to_history(path, report("SE", [club("a")], "2026-11-10T02:00:00Z"))
            self.assertEqual([(h["date"], h["clubs"]) for h in history], [("2026-11-03", 2), ("2026-11-10", 1)])
            with open(path) as f:
                self.assertEqual(len(json.load(f)), 2)

    def test_the_page_lists_the_clubs_escaped(self):
        rep = report("SE", [club("<x>")], "2026-11-03T02:00:00Z")
        text = page([rep], {"SE": [dict(rep["totals"], date="2026-11-03")]})
        self.assertIn("Club &lt;x&gt;", text)
        self.assertIn("holes on the map", text)


if __name__ == "__main__":
    unittest.main()
