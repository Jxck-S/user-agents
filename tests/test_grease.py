"""The GREASE brand list is checked against headers real Chrome builds sent."""

import unittest

from chrome_ua import grease


class GreaseTest(unittest.TestCase):
    # Captured from real Chrome releases. These are the regression anchor: if a
    # refactor breaks the port of Chromium's algorithm, these stop matching.
    KNOWN = {
        120: '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        131: '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    }

    def test_matches_real_chrome_headers(self):
        for major, expected in self.KNOWN.items():
            with self.subTest(major=major):
                self.assertEqual(grease.serialize(grease.brand_list(major)), expected)

    def test_full_version_list_pads_greased_version(self):
        header = grease.serialize(grease.brand_list(131, full_version="131.0.6778.85"))
        self.assertIn('"Not_A Brand";v="24.0.0.0"', header)
        self.assertIn('"Google Chrome";v="131.0.6778.85"', header)

    def test_every_major_yields_three_distinct_brands(self):
        for major in range(90, 250):
            brands = grease.brand_list(major)
            self.assertEqual(len(brands), 3)
            self.assertEqual(len({b["brand"] for b in brands}), 3)
            self.assertTrue(all(b for b in brands), "shuffle left a hole")

    def test_is_deterministic(self):
        self.assertEqual(grease.brand_list(151), grease.brand_list(151))


if __name__ == "__main__":
    unittest.main()
