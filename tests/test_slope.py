"""Slope tables (#2): read by where things are on the page, matched to the club's courses."""
import unittest

from unittest import mock

from golf import slope
from golf.slope import has_calculator, kind, match, read_page


def at(text, x, y, w=60, h=12):
    return {"text": text, "x": x, "y": y, "w": w, "h": h}


def column(x, cr, slope):
    return [at("Course Rating", x, 1046), at(cr, x + 82, 1047, 20), at("Slope Rating", x, 1032), at(slope, x + 85, 1033, 17),
            at("Handicap Spelhcp", x, 1017), at("+4.0 - +3.7 -3", x, 1001)]


class ReadPage(unittest.TestCase):
    def test_columns_by_position_whatever_the_text_order(self):
        lines = (column(312, "69.4", "119") + [at("Vit", 226, 1066, 19, 19)] + column(192, "73.1", "128")
                 + [at("EXEMPEL GK", 356, 1152), at("Norra&Södra · Herrar · Par 72", 340, 1124, 164),
                    at("Banan värderad 2016-06-02", 363, 1100), at("Gul", 345, 1065, 25, 19)])
        self.assertEqual(read_page(lines), {"course": "Norra&Södra", "gender": "men", "par": 72, "rated": "2016-06-02",
                                            "tees": [{"name": "Vit", "cr": 73.1, "slope": 128},
                                                     {"name": "Gul", "cr": 69.4, "slope": 119}]})

    def test_one_line_naming_the_tees_and_no_course_name(self):
        lines = [at("Damer · Par 68", 372, 1125, 100), at("55 50", 200, 1066, 260)] + column(192, "68.3", "113") + column(312, "64.7", "105")
        table = read_page(lines)
        self.assertEqual((table["course"], table["gender"], [t["name"] for t in table["tees"]]), ("", "women", ["55", "50"]))

    def test_a_tee_without_its_name_is_no_table(self):
        self.assertIsNone(read_page([at("Herrar · Par 68", 372, 1125, 100)] + column(192, "63.2", "102")))


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


class Robots(unittest.TestCase):
    def setUp(self):
        slope._robots.clear()
        slope._last.clear()
        self.delay = mock.patch.object(slope, "DELAY", 0)
        self.delay.start()

    def tearDown(self):
        self.delay.stop()

    def answer(self, status, body=""):
        return mock.patch.object(slope, "_curl", lambda url, binary=False: (status, body) if url.endswith("/robots.txt") else (200, "page"))

    def test_what_robots_txt_forbids_is_not_fetched(self):
        with self.answer(200, "User-agent: *\nDisallow: /privat/"):
            self.assertEqual(slope.fetch("https://a.se/privat/x"), (slope.ROBOTS, ""))
            self.assertEqual(slope.fetch("https://a.se/bana"), (200, "page"))

    def test_no_robots_txt_allows_all_but_one_that_cannot_be_reached_allows_none(self):
        with self.answer(404):
            self.assertEqual(slope.fetch("https://b.se/x"), (200, "page"))
        with self.answer(503):
            self.assertEqual(slope.fetch("https://c.se/x"), (slope.ROBOTS, ""))

    def test_robots_txt_is_asked_once_a_site(self):
        calls = []
        with mock.patch.object(slope, "_curl", lambda url, binary=False: calls.append(url) or (404 if url.endswith("robots.txt") else 200, "")):
            slope.fetch("https://d.se/a")
            slope.fetch("https://d.se/b")
        self.assertEqual(calls.count("https://d.se/robots.txt"), 1)


class Survey(unittest.TestCase):
    def test_the_calculator_must_be_set_up_not_just_loaded(self):
        script = '<script src="https://x/widget-slope-calculator-app/app.js"></script>'
        self.assertFalse(has_calculator(script))
        self.assertTrue(has_calculator(script + 'var config = { courseId: "abc" }'))

    def test_how_a_site_came_out(self):
        found = lambda **kw: dict({"pdfs": [], "calculator": None, "problem": None}, **kw)
        self.assertEqual(kind(found()), "none")
        self.assertEqual(kind(found(pdfs=["a.pdf"])), "pdfs")
        self.assertEqual(kind(found(calculator="u")), "calculator")
        self.assertEqual(kind(found(pdfs=["a.pdf"], calculator="u")), "both")
        self.assertEqual(kind(found(problem="u: robots.txt says no")), "robots")
        self.assertEqual(kind(found(problem="u: HTTP 403")), "blocked")
        self.assertEqual(kind(found(problem="u: HTTP 404")), "unreachable")


if __name__ == "__main__":
    unittest.main()
