"""Stable club ids and course keys (format 2): kept week to week, found again when OpenStreetMap's id changes."""
import copy
import unittest

from golf.ids import assign, course_key, format2


def club(osm, name, lat=55.6, lng=13.0, courses=(None,)):
    return {"id": osm, "name": name, "lat": lat, "lng": lng,
            "courses": [{"name": c, "holes": [], "complete": True} for c in courses]}


class Keys(unittest.TestCase):
    def test_a_course_key_comes_from_its_name(self):
        self.assertEqual(course_key("Gamla Banan"), "gamla-banan")
        self.assertEqual(course_key("Pay & Play"), "pay-play")
        self.assertEqual(course_key("Blå"), "bla")
        self.assertEqual(course_key("Holes 10–18"), "10-18")
        self.assertEqual(course_key(None), "main")


class Ids(unittest.TestCase):
    def setUp(self):
        self.week1 = [club("way/1", "Malmö Burlöv Golfklubb", courses=("Holes 1–9", "Holes 10–18")),
                      club("way/2", "Vellinge GK", 55.48, 13.02)]
        self.register, flags = assign("SE", copy.deepcopy(self.week1), {"next": 1, "clubs": {}})
        self.assertEqual(flags, [])

    def ids(self, clubs):
        register, flags = assign("SE", clubs, self.register)
        return {c["name"]: c["id"] for c in clubs}, register, flags

    def test_the_first_week_numbers_the_clubs(self):
        ids, _, _ = self.ids(copy.deepcopy(self.week1))
        self.assertEqual(ids, {"Malmö Burlöv Golfklubb": "se-0001", "Vellinge GK": "se-0002"})

    def test_a_club_keeps_its_id_and_keys_week_to_week(self):
        clubs = copy.deepcopy(self.week1)
        ids, _, flags = self.ids(clubs)
        self.assertEqual(ids["Vellinge GK"], "se-0002")
        self.assertEqual([c["key"] for c in clubs[0]["courses"]], ["1-9", "10-18"])
        self.assertEqual(clubs[0]["osm"], "way/1")
        self.assertEqual(flags, [])

    def test_a_new_osm_id_with_the_same_name_keeps_the_id(self):
        moved = copy.deepcopy(self.week1)
        moved[1]["id"] = "relation/9"   # the outline redrawn as a relation
        ids, register, flags = self.ids(moved)
        self.assertEqual(ids["Vellinge GK"], "se-0002")
        self.assertEqual(register["clubs"]["se-0002"]["osm"], "relation/9")
        self.assertTrue(any("is now relation/9" in f for f in flags))

    def test_renamed_but_in_place_keeps_the_id(self):
        renamed = copy.deepcopy(self.week1)
        renamed[1].update(id="relation/9", name="Vellinge Golfklubb")
        ids, _, _ = self.ids(renamed)
        self.assertEqual(ids["Vellinge Golfklubb"], "se-0002")

    def test_a_new_club_gets_the_next_id(self):
        clubs = copy.deepcopy(self.week1) + [club("way/3", "Öresunds Golfklubb", 55.9, 12.7, courses=())]
        ids, register, _ = self.ids(clubs)
        self.assertEqual(ids["Öresunds Golfklubb"], "se-0003")
        self.assertEqual(register["next"], 4)

    def test_two_possible_clubs_are_flagged_not_guessed(self):
        split = [club("way/1", "Malmö Burlöv Golfklubb"), club("way/2", "Vellinge GK", 55.48, 13.02)]
        register, _ = assign("SE", split, {"next": 1, "clubs": {}})
        # Both outlines redrawn in one week, and a new one lies within 500 m of both old places.
        register["clubs"]["se-0002"].update(lat=55.6, lng=13.0)
        clubs = [club("relation/7", "Burlöv Golf", 55.6, 13.0)]
        clubs, (register, flags) = clubs, assign("SE", clubs, register)
        self.assertEqual(clubs[0]["id"], "se-0003")
        self.assertTrue(any("could be any of se-0001, se-0002" in f for f in flags), flags)

    def test_a_club_gone_keeps_its_id_in_the_register(self):
        _, register, flags = self.ids(copy.deepcopy(self.week1[:1]))
        self.assertIn("se-0002", register["clubs"])
        self.assertTrue(any("se-0002: Vellinge GK (way/2) is gone" in f for f in flags))

    def test_a_new_course_keeps_the_keys_of_the_others(self):
        clubs = copy.deepcopy(self.week1)
        clubs[0]["courses"].insert(0, {"name": "Korthålsbana", "holes": [], "complete": True})
        self.ids(clubs)
        self.assertEqual([c["key"] for c in clubs[0]["courses"]], ["korthalsbana", "1-9", "10-18"])

    def test_a_course_renamed_to_the_same_key_keeps_it(self):
        clubs = copy.deepcopy(self.week1)
        clubs[0]["courses"] = [{"name": "1–9", "holes": [], "complete": True}, {"name": "10–18", "holes": [], "complete": True}]
        _, register, _ = self.ids(clubs)
        self.assertEqual([c["key"] for c in clubs[0]["courses"]], ["1-9", "10-18"])
        self.assertEqual(register["clubs"]["se-0001"]["keys"], {"1–9": "1-9", "10–18": "10-18"})

    def test_two_courses_with_one_key_get_a_number(self):
        clubs = [club("way/5", "Two", courses=("Gul", "gul!"))]
        assign("SE", clubs, {"next": 1, "clubs": {}})
        self.assertEqual([c["key"] for c in clubs[0]["courses"]], ["gul", "gul-2"])


class Format2(unittest.TestCase):
    def test_combinations_name_the_keys_of_their_loops(self):
        c = club("way/1", "Burlöv", courses=("Holes 1–9", "Holes 10–18"))
        c["combos"] = [{"name": "Holes 1–9 + Holes 10–18", "courses": [0, 1]}, {"name": "Holes 10–18 + Holes 1–9", "courses": [1, 0]}]
        assign("SE", [c], {"next": 1, "clubs": {}})
        out = format2(c)
        self.assertEqual((out["id"], out["osm"]), ("se-0001", "way/1"))
        self.assertEqual(out["combos"], [{"key": "1-9+10-18", "name": "Holes 1–9 + Holes 10–18", "loops": ["1-9", "10-18"]},
                                         {"key": "10-18+1-9", "name": "Holes 10–18 + Holes 1–9", "loops": ["10-18", "1-9"]}])
        self.assertEqual([x["key"] for x in out["courses"]], ["1-9", "10-18"])


if __name__ == "__main__":
    unittest.main()
