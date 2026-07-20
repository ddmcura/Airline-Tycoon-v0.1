import unittest

from game.utils.time_utils import advance_game_day


class FixedRandom:
    def uniform(self, _low, _high):
        return 0.0


def make_state():
    return {
        "player_info": {
            "airline_name": "Test Air",
            "current_focus": "Test Air",
        },
        "settings": {"difficulty": "Normal"},
        "game_time": {"current_date": "2026-07-20 00:00"},
        "aircraft_reference": {
            "TestJet": {
                "capacity": 100,
                "cruise_speed_kph": 500,
                "fuel_burn_lph": 1000,
            }
        },
        "airline_list": {
            "Test Air": {
                "finances": {"cash_on_hand": 10000},
                "routes": {
                    "AAA-BBB": {
                        "base_daily_demand": 75,
                        "suggested_pricing": {"Economy": 100, "Business": 200, "First": 500},
                        "distance_km": 1000,
                        "pricing": {
                            "Economy": 100,
                            "Business": 200,
                            "First": 500,
                        },
                        "status": "Planned",
                        "assigned_aircraft": [],
                    }
                },
                "fleet": {
                    "TEST-1": {
                        "model": "TestJet",
                        "status": "active",
                        "delivery_status": "delivered",
                        "layout": {
                            "economy": {"seats": 100},
                            "business_class": {"seats": 0},
                            "first_class": {"seats": 0},
                        },
                        "schedule": {
                            "Mon": {
                                "AAA-BBB": [
                                    {
                                        "start_time": "08:00",
                                        "end_time": "10:00",
                                    }
                                ]
                            }
                        },
                    }
                },
            }
        },
    }


class DailyTickTests(unittest.TestCase):
    def test_advance_day_operates_flights_and_updates_totals(self):
        state = make_state()

        summary = advance_game_day(state, rng=FixedRandom())

        self.assertEqual(state["game_time"]["current_date"], "2026-07-21 00:00")
        self.assertEqual(summary["flights"], 1)
        self.assertEqual(summary["passengers"], 75)
        self.assertEqual(summary["available_seats"], 100)
        self.assertEqual(summary["revenue"], 7500.0)
        self.assertEqual(summary["expenses"], 5200.0)
        self.assertEqual(summary["profit"], 2300.0)
        self.assertEqual(summary["fuel_expenses"], 1700.0)
        self.assertEqual(summary["non_fuel_expenses"], 3500.0)

        airline = state["airline_list"]["Test Air"]
        self.assertEqual(airline["finances"]["cash_on_hand"], 12300.0)
        self.assertEqual(airline["finances"]["total_profit"], 2300.0)
        self.assertEqual(len(airline["finances"]["daily_history"]), 1)

        route = airline["routes"]["AAA-BBB"]
        self.assertEqual(route["status"], "Active")
        self.assertEqual(route["assigned_aircraft"], ["TEST-1"])
        self.assertEqual(route["statistics"]["flights"], 1)
        self.assertEqual(route["statistics"]["passengers"], 75)

        aircraft_stats = airline["fleet"]["TEST-1"]["statistics"]
        self.assertEqual(aircraft_stats["cycles"], 1)
        self.assertEqual(aircraft_stats["flight_hours"], 2.0)

    def test_missing_route_is_skipped_without_charging_airline(self):
        state = make_state()
        aircraft = state["airline_list"]["Test Air"]["fleet"]["TEST-1"]
        aircraft["schedule"]["Mon"] = {"MISSING": [{"start_time": "08:00"}]}

        summary = advance_game_day(state, rng=FixedRandom())

        self.assertEqual(summary["flights"], 0)
        self.assertEqual(summary["skipped_flights"], 1)
        self.assertEqual(summary["profit"], 0.0)
        self.assertEqual(
            state["airline_list"]["Test Air"]["finances"]["cash_on_hand"],
            10000.0,
        )

    def test_inactive_aircraft_does_not_operate(self):
        state = make_state()
        state["airline_list"]["Test Air"]["fleet"]["TEST-1"]["status"] = "maintenance"

        summary = advance_game_day(state, rng=FixedRandom())

        self.assertEqual(summary["flights"], 0)
        self.assertEqual(summary["passengers"], 0)

    def test_deadhead_costs_money_without_passengers_or_demand(self):
        state = make_state()
        aircraft = state["airline_list"]["Test Air"]["fleet"]["TEST-1"]
        block = aircraft["schedule"]["Mon"]["AAA-BBB"][0]
        block["service_type"] = "deadhead"

        summary = advance_game_day(state, rng=FixedRandom())

        self.assertEqual(summary["flights"], 1)
        self.assertEqual(summary["deadhead_flights"], 1)
        self.assertEqual(summary["passengers"], 0)
        self.assertEqual(summary["available_seats"], 0)
        self.assertEqual(summary["revenue"], 0)
        self.assertEqual(summary["expenses"], 5200.0)
        self.assertEqual(summary["profit"], -5200.0)


if __name__ == "__main__":
    unittest.main()
