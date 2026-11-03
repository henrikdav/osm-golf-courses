"""A club file's loop from a course entered in the app: the scorecard's par, index and lengths."""
import unittest

from golf.from_app import loop_from


def holes(pars, index, lengths):
    return [{"par": p, "index": i, "lengths": {"48": m, "43": m - 20 if m else None}} for p, i, m in zip(pars, index, lengths)]


class LoopFrom(unittest.TestCase):
    def test_a_course_played_alone_keeps_its_printed_index_and_its_ranking(self):
        loop, notes = loop_from(holes([4, 3, 5], [4, 2, 6], [300, 150, 450]), {"holes": [{"par": 4}, {"par": 3}, {"par": 5}]}, "main")
        self.assertEqual((loop["index"], loop["ranking"]), ([4, 2, 6], [2, 1, 3]))
        self.assertEqual(loop["tees"], {"48": [300, 150, 450], "43": [280, 130, 430]})
        self.assertNotIn("par", loop)

    def test_par_that_differs_from_osm_is_a_correction_saying_so(self):
        loop, notes = loop_from(holes([4, 3, 5], [1, 2, 3], [300, 150, 450]), {"holes": [{"par": 4}, {"par": None}, {"par": 4}]}, "main")
        self.assertEqual(loop["par"], {"2": 3, "3": 5})
        self.assertIn("other par", loop["why"])

    def test_a_tee_with_missing_lengths_is_left_out_and_said(self):
        loop, notes = loop_from(holes([4, 3, 5], [1, 2, 3], [300, None, 450]), {"holes": [{"par": 4}, {"par": 3}, {"par": 5}]}, "main")
        self.assertNotIn("48", loop.get("tees", {}))
        self.assertTrue(any("tee 48" in n for n in notes))

    def test_a_new_course_carries_its_name_and_par(self):
        loop, _ = loop_from(holes([4, 3], [2, 1], [300, 150]), None, "main", new_name="Knistad")
        self.assertEqual(loop["new"], {"name": "Knistad", "par": [4, 3]})


if __name__ == "__main__":
    unittest.main()
