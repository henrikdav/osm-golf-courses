"""The report of what the data has: each club's level and what it lacks, the totals, and the history."""
import json
import os
import tempfile
import unittest

from golf.report import add_to_history, club_row, page, report


def course(key, pars, index=None, complete=True, tees=None):
    c = {"key": key, "name": key, "complete": complete, "notes": [],
         "holes": [{"n": i + 1, "par": p, "index": index[i] if index else None} for i, p in enumerate(pars)]}
    if tees:
        c["tees"] = tees
    return c


def club(cid, courses=(), combos=None, **more):
    out = {"id": cid, "name": "Club " + cid, "courses": list(courses)}
    if combos:
        out["combos"] = combos
    out.update(more)
    return out


NINE = [4] * 9


class Levels(unittest.TestCase):
    def test_each_level_and_what_it_lacks(self):
        self.assertEqual(club_row(club("a"))["lacks"], "holes on the map")
        self.assertEqual(club_row(club("b", [course("main", NINE, complete=False)]))["level"], 1)
        self.assertEqual(club_row(club("c", [course("main", [4] * 8 + [None])]))["lacks"], "par on every hole")
        self.assertEqual(club_row(club("d", [course("main", [4] * 18)]))["lacks"], "hole index")
        row = club_row(club("e", [course("main", NINE, index=list(range(1, 10)))]))
        self.assertEqual((row["level"], row["lacks"]), (3, "lengths per tee (club file)"))
        tees = [{"name": "48", "lengths": [300] * 9}]
        self.assertEqual(club_row(club("f", [course("main", NINE, index=list(range(1, 10)), tees=tees)]))["level"], 4)

    def test_a_combination_counts_with_its_own_index(self):
        loops = [course("1-9", NINE), course("10-18", NINE)]
        bare = club("g", loops, combos=[{"key": "1-9+10-18", "name": "1–18", "loops": ["1-9", "10-18"]}])
        self.assertEqual(club_row(bare)["level"], 2)
        indexed = club("h", loops, combos=[{"key": "1-9+10-18", "name": "1–18", "loops": ["1-9", "10-18"],
                                            "index": list(range(1, 19))}], clubFile={"what": "x"})
        row = club_row(indexed)
        self.assertEqual((row["level"], row["indexed"], row["clubFile"]), (3, ["1–18"], True))


class Report(unittest.TestCase):
    def test_totals_and_the_best_clubs_first(self):
        rep = report("SE", [club("a"), club("d", [course("main", [4] * 18)])], "2026-11-03T02:00:00Z")
        self.assertEqual(rep["totals"]["name only"], 1)
        self.assertEqual(rep["totals"]["par"], 1)
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
