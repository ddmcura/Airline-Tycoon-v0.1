"""Regression tests for the directional demand model."""

import unittest

from game.economy.demand import (
    DEMAND_MODEL_VERSION,
    calculate_adjusted_daily_demand,
    calculate_directional_base_demand,
    calculate_distance_multiplier,
)


class DemandModelTests(unittest.TestCase):
    def test_mnl_to_dvo_design_example(self):
        demand = calculate_directional_base_demand(
            origin_population=13_500_000,
            destination_population=1_800_000,
            distance_km=960,
        )

        self.assertEqual(demand, 1244)

    def test_demand_is_directional(self):
        outbound = calculate_directional_base_demand(
            13_500_000,
            1_800_000,
            960,
        )
        return_trip = calculate_directional_base_demand(
            1_800_000,
            13_500_000,
            960,
        )

        self.assertGreater(outbound, return_trip)

    def test_distance_multiplier_matches_design_example(self):
        self.assertAlmostEqual(calculate_distance_multiplier(960), 0.92)

    def test_old_route_is_upgraded_when_adjusted(self):
        route = {
            "origin_population": 13_500_000,
            "destination_population": 1_800_000,
            "distance_km": 960,
            "base_daily_demand": 900,
            "demand_model_version": 2,
            "pricing": {"Economy": 100},
            "suggested_pricing": {"Economy": 100},
        }

        adjusted = calculate_adjusted_daily_demand(route, "Normal")

        self.assertEqual(adjusted, 1244)
        self.assertEqual(route["base_daily_demand"], 1244)
        self.assertEqual(route["demand_model_version"], DEMAND_MODEL_VERSION)

    def test_route_modifiers_are_applied(self):
        route = {
            "origin_population": 13_500_000,
            "destination_population": 1_800_000,
            "distance_km": 960,
            "pricing": {"Economy": 100},
            "suggested_pricing": {"Economy": 100},
            "seasonality_multiplier": 1.20,
            "reputation_multiplier": 1.05,
            "competition_multiplier": 0.50,
        }

        adjusted = calculate_adjusted_daily_demand(route, "Normal")

        self.assertEqual(adjusted, round(1244 * 1.20 * 1.05 * 0.50))


if __name__ == "__main__":
    unittest.main()
