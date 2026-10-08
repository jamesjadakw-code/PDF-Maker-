import unittest

from crm.listing_locations import (
    CORE_CITIES,
    OTHER_CITIES,
    OTHER_EVERY,
    city_for,
    city_hash,
)


class ListingLocationTests(unittest.TestCase):
    def test_format_is_city_comma_state(self):
        for place in CORE_CITIES + OTHER_CITIES:
            city, state = place.split(", ")
            self.assertTrue(city)
            self.assertEqual(len(state), 2)
            self.assertEqual(state, state.upper())

    def test_lists_have_expected_sizes(self):
        self.assertEqual(len(CORE_CITIES), 70)
        self.assertEqual(len(OTHER_CITIES), 30)
        self.assertEqual(len(set(CORE_CITIES)), 70)
        self.assertEqual(len(set(OTHER_CITIES)), 30)

    def test_same_unit_keeps_the_same_city(self):
        self.assertEqual(city_for("u803"), city_for("u803"))
        self.assertEqual(city_for("u842"), city_for("u842"))

    def test_example_format_houston_style(self):
        place = city_for("u803")
        self.assertRegex(place, r"^.+, [A-Z]{2}$")

    def test_other_region_share_is_about_thirty_of_five_forty(self):
        keys = [f"u{n}" for n in range(1, 541)]
        other = [city_for(key) for key in keys if city_for(key) in OTHER_CITIES]
        self.assertGreaterEqual(len(other), 20)
        self.assertLessEqual(len(other), 45)

    def test_core_cities_are_reused(self):
        keys = [f"u{n}" for n in range(1, 541)]
        core = [city_for(key) for key in keys if city_for(key) in CORE_CITIES]
        self.assertGreater(len(core), len(CORE_CITIES))
        self.assertTrue(set(core) <= set(CORE_CITIES))

    def test_hash_is_stable(self):
        self.assertEqual(city_hash("u803"), city_hash("u803"))
        self.assertNotEqual(city_hash("u803"), city_hash("u551"))

    def test_other_bucket_uses_modulo(self):
        key = next(f"u{n}" for n in range(1, 5000) if city_hash(f"u{n}") % OTHER_EVERY == 0)
        self.assertIn(city_for(key), OTHER_CITIES)
