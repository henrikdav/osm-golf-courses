"""Club files (#2): checked against the club's OSM data, and merged into format 2 as additions."""
import copy
import unittest

from golf.clubfiles import apply, apply_overlay, build_overlay, check, merge, overlay


def loop(key, pars, index=None, notes=()):
    return {"key": key, "name": key.replace("-", "–"), "complete": True, "holeCount": len(pars), "notes": list(notes),
            "holes": [{"n": i + 1, "par": p, "index": index[i] if index else None, "path": []} for i, p in enumerate(pars)]}


CLUB = {"id": "se-1", "osm": "way/1", "name": "Loops GK",
        "courses": [loop("1-9", [4, 5, 4, 3, 4, 3, 4, 4, 4], index=[1, 17, 7, 3, 9, 11, 5, 15, 13]),
                    loop("10-18", [4, 4, 4, 3, 5, 4, 4, 3, 5]),
                    loop("19-27", [4, 5, 3, 4, 4, 4, 5, 3, 4], index=[1, 17, 7, 3, 9, 11, 5, 15, 13],
                         notes=["Hole 2 is 309 m for par 5", "Hole 6 is 531 m for par 4", "Hole 9 has no green"])],
        "combos": [{"key": "1-9+10-18", "name": "1–18", "loops": ["1-9", "10-18"]},
                   {"key": "10-18+1-9", "name": "10–18 + 1–9", "loops": ["10-18", "1-9"]}]}

FILE = {"id": "se-1", "name": "Loops GK", "source": {"what": "the club's scorecard", "by": "H", "date": "2026-11-03"},
        "loops": {"1-9": {"ranking": [1, 9, 4, 2, 5, 6, 3, 8, 7], "tees": {"48": [300, 395, 290, 115, 245, 120, 295, 295, 295]}},
                  "10-18": {"ranking": [5, 9, 1, 4, 8, 3, 7, 2, 6]},
                  "19-27": {"ranking": [3, 7, 2, 8, 9, 6, 1, 5, 4], "par": {"2": 4, "6": 5}, "why": "swapped in OSM"}},
        "combos": [{"loops": ["1-9", "10-18"], "odd": "1-9"}, {"loops": ["19-27", "1-9"], "odd": "19-27"}],
        "onlyTheseCombos": True}


class Check(unittest.TestCase):
    def test_a_good_file_has_no_problems(self):
        self.assertEqual(check(FILE, CLUB), [])

    def test_what_is_wrong_is_said(self):
        bad = copy.deepcopy(FILE)
        bad["loops"]["1-9"]["ranking"] = [1, 1, 4, 2, 5, 6, 3, 8, 7]
        bad["loops"]["10-18"]["tees"] = {"48": [300, 395]}
        bad["loops"]["19-27"].pop("why")
        bad["loops"]["28-36"] = {"ranking": list(range(1, 10))}
        bad["combos"].append({"loops": ["1-9", "10-18"], "odd": "19-27"})
        del bad["source"]
        problems = check(bad, CLUB)
        for words in ("ranking must hold 1–9", "tee 48: 9 lengths", "says why", "28-36: no such course",
                      "odd must be one of its loops", "no source"):
            self.assertTrue(any(words in p for p in problems), (words, problems))

    def test_a_correction_osm_has_caught_up_with_can_go(self):
        fixed = copy.deepcopy(CLUB)
        fixed["courses"][2]["holes"][1]["par"] = 4
        self.assertTrue(any("OSM has par 4 now" in p for p in check(FILE, fixed)))


class Overlay(unittest.TestCase):
    def test_joining_the_overlay_gives_what_merging_the_file_gives(self):
        for file in (FILE, dict(FILE, onlyTheseCombos=False),
                     dict(FILE, slope={"1-9+10-18": {"men": {"par": 70, "rated": None, "tees": {"61": {"cr": 70.2, "slope": 130}}}}})):
            self.assertEqual(apply_overlay(CLUB, overlay(file)), merge(CLUB, file))

    def test_the_overlay_holds_only_what_the_file_adds(self):
        extra = overlay(FILE)
        self.assertNotIn("holes", str(extra))
        self.assertEqual(extra["loops"]["19-27"]["par"], {"2": 4, "6": 5})
        self.assertEqual(extra["combos"][0]["key"], "1-9+10-18")
        self.assertEqual(extra["clubFile"], FILE["source"])
        self.assertEqual(extra["loops"]["1-9"]["tees"], [{"name": "48", "lengths": [300, 395, 290, 115, 245, 120, 295, 295, 295]}])

    def test_a_file_that_does_not_check_out_is_left_out_and_said(self):
        bad = dict(FILE, source=None)
        data, flags = build_overlay({"se-1": bad, "se-2": FILE}, [CLUB], "2026-11-06T00:00:00Z")
        self.assertEqual(data["clubs"], {})
        self.assertEqual(len(flags), 2)
        data, flags = build_overlay({"se-1": FILE}, [CLUB], "2026-11-06T00:00:00Z")
        self.assertEqual((list(data["clubs"]), flags, data["format"]), (["se-1"], [], 1))


class Merge(unittest.TestCase):
    def setUp(self):
        self.out = merge(CLUB, FILE)

    def test_the_club_is_left_as_it_was(self):
        self.assertEqual(CLUB["courses"][2]["holes"][1]["par"], 5)

    def test_par_corrected_and_its_osm_notes_dropped(self):
        holes = self.out["courses"][2]["holes"]
        self.assertEqual((holes[1]["par"], holes[5]["par"]), (4, 5))
        self.assertEqual(self.out["courses"][2]["notes"], ["Hole 9 has no green"])

    def test_a_loop_s_index_is_its_ranking(self):
        self.assertEqual([h["index"] for h in self.out["courses"][2]["holes"]], [3, 7, 2, 8, 9, 6, 1, 5, 4])

    def test_tees_with_their_lengths(self):
        self.assertEqual(self.out["courses"][0]["tees"], [{"name": "48", "lengths": [300, 395, 290, 115, 245, 120, 295, 295, 295]}])
        self.assertNotIn("tees", self.out["courses"][1])

    def test_only_the_club_s_combinations_with_their_index(self):
        combos = self.out["combos"]
        self.assertEqual([c["key"] for c in combos], ["1-9+10-18", "19-27+1-9"])
        self.assertEqual(combos[0]["name"], "1–18")
        self.assertEqual(combos[0]["index"], [1, 17, 7, 3, 9, 11, 5, 15, 13, 10, 18, 2, 8, 16, 6, 14, 4, 12])
        self.assertEqual(combos[1]["index"][9:], [2, 18, 8, 4, 10, 12, 6, 16, 14], "the odd loop first, 1–9 even")
        self.assertEqual(combos[1]["name"], "19–27 + 1–9", "named from its loops when OSM had no such pair")

    def test_without_only_these_the_other_combinations_are_kept(self):
        some = dict(FILE, onlyTheseCombos=False, combos=[{"loops": ["1-9", "10-18"], "odd": "1-9"}])
        combos = merge(CLUB, some)["combos"]
        self.assertEqual(sorted(c["key"] for c in combos), ["1-9+10-18", "10-18+1-9"])
        self.assertIn("index", next(c for c in combos if c["key"] == "1-9+10-18"))
        self.assertNotIn("index", next(c for c in combos if c["key"] == "10-18+1-9"))

    def test_the_scorecard_s_own_index_wins_over_the_ranking(self):
        printed = copy.deepcopy(FILE)
        printed["loops"]["1-9"]["index"] = [2, 18, 8, 4, 10, 12, 6, 16, 14]
        self.assertEqual(check(printed, CLUB), [])
        self.assertEqual([h["index"] for h in merge(CLUB, printed)["courses"][0]["holes"]], [2, 18, 8, 4, 10, 12, 6, 16, 14])

    def test_a_course_not_on_the_map_is_added_without_positions(self):
        new = {"id": "se-2", "name": "New GK", "source": {"what": "card"},
               "loops": {"main": {"new": {"name": "Main", "par": [4, 3, 5]}, "index": [3, 1, 2],
                                  "tees": {"58": [300, 150, 450]}}}}
        club = {"id": "se-2", "osm": "way/2", "name": "New GK", "courses": []}
        self.assertEqual(check(new, club), [])
        course = merge(club, new)["courses"][0]
        self.assertEqual((course["key"], course["mapped"], [h["par"] for h in course["holes"]], [h["index"] for h in course["holes"]]),
                         ("main", False, [4, 3, 5], [3, 1, 2]))
        self.assertEqual(course["tees"][0]["lengths"], [300, 150, 450])
        mapped = dict(club, courses=[{"key": "main", "holes": [{"n": 1}]}])
        self.assertTrue(any("no longer new" in p for p in check(new, mapped)))

    def test_the_source_goes_with_it(self):
        self.assertEqual(self.out["clubFile"]["what"], "the club's scorecard")


class Slope(unittest.TestCase):
    TABLE = {"par": 71, "rated": "2017-09-19", "tees": {"61": {"cr": 71.8, "slope": 136}, "48": {"cr": 66.1, "slope": 124}}}

    def file(self, slope):
        return dict(FILE, slope=slope, source=dict(FILE["source"], slope={"tables": ["x.pdf"], "read": "2026-11-05"}))

    def test_on_a_combination_and_a_loop(self):
        out = merge(CLUB, self.file({"1-9+10-18": {"men": self.TABLE}, "1-9": {"women": dict(self.TABLE, par=70)}}))
        combo = next(c for c in out["combos"] if c["key"] == "1-9+10-18")
        self.assertEqual(combo["slope"]["men"]["tees"][0], {"name": "61", "cr": 71.8, "slope": 136})
        self.assertEqual(out["courses"][0]["slope"]["women"]["par"], 70)

    def test_checked(self):
        self.assertEqual(check(self.file({"1-9+10-18": {"men": self.TABLE}}), CLUB), [])
        bad = {"10-18+1-9": {"men": self.TABLE},   # not among onlyTheseCombos
               "1-9": {"juniors": self.TABLE, "men": dict(self.TABLE, tees={"61": {"cr": 7.18, "slope": 136}})}}
        problems = check(self.file(bad), CLUB)
        for words in ("10-18+1-9: no such course", "1-9 juniors: men or women", "tee 61: course rating"):
            self.assertTrue(any(words in p for p in problems), (words, problems))
        self.assertTrue(any("under source" in p for p in check(dict(FILE, slope={"1-9": {"men": self.TABLE}}), CLUB)))


class Apply(unittest.TestCase):
    def test_merged_where_there_is_a_file_and_it_is_good(self):
        clubs, flags = apply([copy.deepcopy(CLUB)], {"se-1": FILE})
        self.assertEqual(flags, [])
        self.assertIn("clubFile", clubs[0])

    def test_a_file_with_problems_is_left_out_and_said(self):
        bad = dict(FILE, source=None)
        clubs, flags = apply([copy.deepcopy(CLUB)], {"se-1": bad, "se-9": FILE})
        self.assertNotIn("clubFile", clubs[0])
        self.assertTrue(any("se-1: no source" in f for f in flags))
        self.assertTrue(any("se-9: no such club" in f for f in flags))


if __name__ == "__main__":
    unittest.main()
