"""The cleaning, tested on saved Overpass answers for clubs that each map their courses differently.

The fixtures are each club's outline with the hole lines and greens in its bounding box, as Overpass gave them on
2026-10-24 (`build.py` fetches the whole country the same way).
"""
import copy
import json
import os
import unittest

from golf.clean import clean, combos, length

HERE = os.path.dirname(__file__)


def club(fixture, name=None):
    with open(os.path.join(HERE, "fixtures", fixture + ".json")) as f:
        data = json.load(f)
    clubs, _ = clean(data["outlines"], data["holes"], data["greens"])
    return next(c for c in clubs if name is None or c["name"] == name)


def summary(c):
    return [(x["name"], len(x["holes"]), x["complete"]) for x in c["courses"]]


class OneCourse(unittest.TestCase):
    def test_vellinge_is_one_course_without_par(self):
        c = club("vellinge")
        self.assertEqual(summary(c), [(None, 18, True)])
        self.assertIn("No par", c["courses"][0]["notes"])
        self.assertNotIn("combos", c)

    def test_a_hole_runs_from_the_back_tee_to_the_pin(self):
        hole = club("vellinge")["courses"][0]["holes"][0]
        self.assertEqual(hole["n"], 1)
        self.assertGreater(len(hole["path"]), 1)
        self.assertTrue(200 < length(hole["path"]) < 500, length(hole["path"]))


class ByCourseName(unittest.TestCase):
    def test_bokskogen_has_two_courses_by_golf_course_name(self):
        c = club("bokskogen")
        self.assertEqual(summary(c), [("Gamla Banan", 18, True), ("Kungsbanan", 18, True)])
        for x in c["courses"]:
            self.assertTrue(all(h["par"] and h["index"] for h in x["holes"]))
            self.assertEqual(sorted(h["index"] for h in x["holes"]), list(range(1, 19)))

    def test_nine_hole_loops_by_course_name_are_offered_two_by_two(self):
        # Örestad's loops, with their names moved from the hole's name to golf:course:name.
        with open(os.path.join(HERE, "fixtures", "orestad.json")) as f:
            data = json.load(f)
        for line in data["holes"]:
            tags = line["tags"]
            if tags.get("name", "").startswith(("Blå", "Gul", "Röd")):
                tags["golf:course:name"] = tags.pop("name").split(" ")[0]
        clubs, _ = clean(data["outlines"], data["holes"], data["greens"])
        c = next(x for x in clubs if x["name"] == "Örestads golfklubb")
        self.assertEqual({x["name"] for x in c["courses"]}, {"Blå", "Gul", "Röd", "Pay & Play"})
        self.assertEqual(len(c["combos"]), 6)


class ByHoleName(unittest.TestCase):
    def test_orestad_loops_come_from_the_hole_names(self):
        c = club("orestad")
        self.assertEqual(summary(c), [("Blå", 9, True), ("Gul", 9, True), ("Pay & Play", 18, True), ("Röd", 9, True)])

    def test_two_loops_one_after_the_other_for_eighteen_holes(self):
        c = club("orestad")
        names = {x["name"] for x in c["combos"]}
        self.assertEqual(names, {"Blå + Gul", "Blå + Röd", "Gul + Blå", "Gul + Röd", "Röd + Blå", "Röd + Gul"})
        blue_yellow = next(x for x in c["combos"] if x["name"] == "Blå + Gul")
        self.assertEqual([c["courses"][i]["name"] for i in blue_yellow["courses"]], ["Blå", "Gul"])

    def test_the_18_hole_pay_and_play_is_no_loop(self):
        c = club("orestad")
        self.assertFalse(any("Pay & Play" in x["name"] for x in c["combos"]))


class RunOf27(unittest.TestCase):
    def test_malmo_burlov_1_to_27_becomes_three_loops(self):
        c = club("malmo-burlov")
        self.assertEqual(summary(c), [("Holes 1–9", 9, True), ("Holes 10–18", 9, True), ("Holes 19–27", 9, True)])
        self.assertEqual([h["n"] for h in c["courses"][1]["holes"]], list(range(1, 10)), "renumbered 1–9")
        self.assertEqual(len(c["combos"]), 6)

    def test_a_hole_too_long_or_short_for_its_par_is_noted(self):
        notes = club("malmo-burlov")["courses"][2]["notes"]
        self.assertIn("Hole 2 is 309 m for par 5", notes)


class Twins(unittest.TestCase):
    def test_bastad_every_number_twice_far_apart_is_two_courses(self):
        c = club("bastad")
        self.assertEqual(summary(c), [("Course 1", 18, True), ("Course 2", 18, True)])
        # Each course follows on: a hole's tee is near the previous hole's green, not across the grounds.
        for x in c["courses"]:
            holes = x["holes"]
            gaps = [length([holes[i]["path"][-1], holes[i + 1]["path"][0]]) for i in range(len(holes) - 1)]
            self.assertLess(max(gaps), 400, gaps)

    def test_landeryd_a_hole_drawn_twice_at_one_spot_is_kept_once(self):
        c = club("landeryd", "Landeryds Golfklubb")
        complete = [x for x in c["courses"] if x["complete"]]
        self.assertTrue(complete, summary(c))
        self.assertFalse(any(n.startswith("Numbered twice") for x in complete for n in x["notes"]))


class Counts(unittest.TestCase):
    def test_counts_for_the_checks(self):
        with open(os.path.join(HERE, "fixtures", "bokskogen.json")) as f:
            data = json.load(f)
        _, counts = clean(data["outlines"], data["holes"], data["greens"])
        self.assertEqual(counts["clubs"], 1)
        self.assertEqual(counts["completeCourses"], 2)

    def test_combos_need_complete_named_nine_hole_loops(self):
        loop = {"name": "A", "complete": True, "holes": [{}] * 9}
        self.assertEqual(combos([loop, dict(loop, name="B")])[0]["name"], "A + B")
        self.assertEqual(combos([loop, dict(loop, name="B", complete=False)]), [])
        self.assertEqual(combos([loop, dict(loop, name=None)]), [])


if __name__ == "__main__":
    unittest.main()
