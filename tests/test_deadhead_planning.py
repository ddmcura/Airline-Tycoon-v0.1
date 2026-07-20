import unittest

from game.scheduling.deadhead import plan_deadhead


AIRPORTS = {
    "MNL": {"coordinates": {"lat": 14.5, "lon": 121.0}},
    "DVO": {"coordinates": {"lat": 7.1, "lon": 125.6}},
    "CEB": {"coordinates": {"lat": 10.3, "lon": 123.9}},
}


class DeadheadPlanningTests(unittest.TestCase):
    def test_no_deadhead_when_aircraft_is_at_origin(self):
        plan = plan_deadhead([], 420, "MNL", "MNL", 800, AIRPORTS)
        self.assertIsNone(plan)

    def test_deadhead_is_planned_after_previous_arrival(self):
        existing = [
            {
                "start_time": "07:00",
                "end_time": "08:40",
                "start_airport": "MNL",
                "end_airport": "DVO",
            }
        ]

        plan = plan_deadhead(existing, 540, "MNL", "MNL", 800, AIRPORTS)

        self.assertEqual(plan["route_id"], "DVO-MNL")
        self.assertEqual(plan["start"], 520)
        self.assertGreater(plan["passenger_start"], plan["end"])

    def test_aircraft_can_continue_directly_from_last_destination(self):
        existing = [
            {
                "start_time": "07:00",
                "end_time": "08:40",
                "start_airport": "MNL",
                "end_airport": "DVO",
            }
        ]

        plan = plan_deadhead(existing, 540, "DVO", "MNL", 800, AIRPORTS)

        self.assertIsNone(plan)

    def test_deadhead_must_be_within_aircraft_range(self):
        plan = plan_deadhead(
            [], 420, "DVO", "MNL", 800, AIRPORTS, max_range_km=100
        )

        self.assertIn("error", plan)
        self.assertIn("beyond", plan["error"])


if __name__ == "__main__":
    unittest.main()
