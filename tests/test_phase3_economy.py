import unittest

from game.economy.currency import convert_from_usd, format_money, set_display_currency
from game.economy.demand import (
    backfill_route_demand,
    calculate_adjusted_daily_demand,
    calculate_directional_base_demand,
    price_demand_multiplier,
)
from game.route_management.route_factory import build_directional_route_pair
from game.utils.time_utils import advance_game_day
from tests.test_daily_tick import FixedRandom, make_state


class Phase3EconomyTests(unittest.TestCase):
    def test_legacy_route_gets_population_and_demand_backfill(self):
        route = {}
        airport_index = {
            "BIG": {
                "name": "Big Airport",
                "country": "Testland",
                "population": 10_000_000,
                "coordinates": {"lat": 0, "lon": 0},
            },
            "SML": {
                "name": "Small Airport",
                "country": "Testland",
                "population": 1_000_000,
                "coordinates": {"lat": 0, "lon": 4.5},
            },
        }

        demand = backfill_route_demand(route, airport_index, "BIG-SML")

        self.assertGreater(demand, 0)
        self.assertEqual(route["origin_iata"], "BIG")
        self.assertEqual(route["destination_iata"], "SML")
        self.assertEqual(route["origin_population"], 10_000_000)
        self.assertEqual(route["destination_population"], 1_000_000)
        self.assertEqual(route["suggested_pricing"], route["pricing"])

    def test_directional_demand_favors_larger_origin(self):
        large_to_small = calculate_directional_base_demand(
            10_000_000, 1_000_000, 500
        )
        small_to_large = calculate_directional_base_demand(
            1_000_000, 10_000_000, 500
        )
        self.assertGreater(large_to_small, small_to_large)

    def test_easy_ignores_price_sensitivity(self):
        self.assertEqual(price_demand_multiplier("Easy", 200, 100), 1.0)
        self.assertEqual(price_demand_multiplier("Easy", 50, 100), 1.0)

    def test_higher_difficulties_penalize_expensive_fares_more(self):
        normal = price_demand_multiplier("Normal", 125, 100)
        hard = price_demand_multiplier("Hard", 125, 100)
        extreme = price_demand_multiplier("Extreme", 125, 100)
        self.assertGreater(normal, hard)
        self.assertGreater(hard, extreme)

    def test_route_factory_creates_linked_asymmetric_directions(self):
        large = {
            "iata": "BIG",
            "name": "Large City Airport",
            "country": "Testland",
            "population": 10_000_000,
            "coordinates": {"lat": 0.0, "lon": 0.0},
        }
        small = {
            "iata": "SML",
            "name": "Small City Airport",
            "country": "Testland",
            "population": 1_000_000,
            "coordinates": {"lat": 0.0, "lon": 4.5},
        }

        routes = build_directional_route_pair(large, small)

        self.assertEqual(set(routes), {"BIG-SML", "SML-BIG"})
        self.assertEqual(routes["BIG-SML"]["reverse_route_id"], "SML-BIG")
        self.assertEqual(routes["SML-BIG"]["reverse_route_id"], "BIG-SML")
        self.assertGreater(
            routes["BIG-SML"]["base_daily_demand"],
            routes["SML-BIG"]["base_daily_demand"],
        )

    def test_display_currency_converts_without_changing_usd_value(self):
        state = {"settings": {"display_currency": "USD"}}
        set_display_currency(state, "PHP")
        self.assertEqual(convert_from_usd(state, 100), 5800)
        self.assertEqual(format_money(state, 100), "P5,800.00")

    def test_multiple_flights_share_one_directional_demand_pool(self):
        state = make_state()
        route = state["airline_list"]["Test Air"]["routes"]["AAA-BBB"]
        route["base_daily_demand"] = 120
        aircraft = state["airline_list"]["Test Air"]["fleet"]["TEST-1"]
        aircraft["schedule"]["Mon"]["AAA-BBB"].append(
            {"start_time": "14:00", "end_time": "16:00"}
        )

        summary = advance_game_day(state, rng=FixedRandom())

        self.assertEqual(summary["flights"], 2)
        self.assertEqual(summary["passengers"], 120)
        self.assertEqual(summary["available_seats"], 200)

    def test_price_changes_adjust_normal_demand(self):
        route = {
            "base_daily_demand": 100,
            "suggested_pricing": {"Economy": 100},
            "pricing": {"Economy": 125},
        }
        self.assertEqual(calculate_adjusted_daily_demand(route, "Normal"), 85)


if __name__ == "__main__":
    unittest.main()
