"""Slope tables (#2): read by where things are on the page, matched to the club's courses."""
import unittest

from golf.slope import match, read_page


def at(text, x, y, w=60, h=12):
    return {"text": text, "x": x, "y": y, "w": w, "h": h}


def column(x, cr, slope):
    return [at("Course Rating", x, 1046), at(cr, x + 82, 1047, 20), at("Slope Rating", x, 1032), at(slope, x + 85, 1033, 17),
            at("Handicap Spelhcp", x, 1017), at("+4.0 - +3.7 -3", x, 1001)]


class ReadPage(unittest.TestCase):
    def test_columns_by_position_whatever_the_text_order(self):
        lines = (column(312, "70.3", "122") + [at("Vit", 226, 1066, 19, 19)] + column(192, "72.6", "126")
                 + [at("ÖRESTADS GK", 356, 1152), at("Blå&Gul · Herrar · Par 71", 340, 1124, 164),
                    at("Banan värderad 2018-04-18", 363, 1100), at("Gul", 345, 1065, 25, 19)])
        self.assertEqual(read_page(lines), {"course": "Blå&Gul", "gender": "men", "par": 71, "rated": "2018-04-18",
                                            "tees": [{"name": "Vit", "cr": 72.6, "slope": 126},
                                                     {"name": "Gul", "cr": 70.3, "slope": 122}]})

    def test_one_line_naming_the_tees_and_no_course_name(self):
        lines = [at("Damer · Par 68", 372, 1125, 100), at("57 53", 200, 1066, 260)] + column(192, "70.2", "117") + column(312, "66.3", "109")
        table = read_page(lines)
        self.assertEqual((table["course"], table["gender"], [t["name"] for t in table["tees"]]), ("", "women", ["57", "53"]))

    def test_a_tee_without_its_name_is_no_table(self):
        self.assertIsNone(read_page([at("Herrar · Par 68", 372, 1125, 100)] + column(192, "65.4", "108")))


class Match(unittest.TestCase):
    CLUB = {"courses": [{"key": "1-9", "name": "1–9", "complete": True}, {"key": "10-18", "name": "10–18", "complete": True}],
            "combos": [{"key": "1-9+10-18", "name": "1–18", "loops": ["1-9", "10-18"]}]}

    def test_by_name_a_loop_and_a_combination(self):
        self.assertEqual(match({"course": "Hål 1-9"}, self.CLUB), "1-9")
        self.assertEqual(match({"course": "1–18"}, self.CLUB), "1-9+10-18")
        self.assertEqual(match({"course": "1-9+10-18"}, self.CLUB), "1-9+10-18")
        self.assertIsNone(match({"course": "Korthål"}, self.CLUB))

    def test_the_club_s_only_course_whatever_it_is_called(self):
        self.assertEqual(match({"course": ""}, {"courses": [{"key": "main", "name": None, "complete": True}]}), "main")


if __name__ == "__main__":
    unittest.main()
