import unittest

from game.scheduling.planning import route_demand_metrics
from tests.test_daily_tick import make_state


class SchedulingPlanningTests(unittest.TestCase):
    def test_demand_left_subtracts_scheduled_directional_seats(self):
        state = make_state()
        route = state["airline_list"]["Test Air"]["routes"]["AAA-BBB"]
        route["base_daily_demand"] = 150

        metrics = route_demand_metrics(state, {"AAA-BBB": route})

        self.assertEqual(metrics["AAA-BBB"]["demand"], 150)
        self.assertEqual(metrics["AAA-BBB"]["assigned_seats"], 100)
        self.assertEqual(metrics["AAA-BBB"]["demand_left"], 50)

    def test_deadhead_does_not_consume_passenger_demand(self):
        state = make_state()
        aircraft = state["airline_list"]["Test Air"]["fleet"]["TEST-1"]
        aircraft["schedule"]["Mon"]["AAA-BBB"][0]["service_type"] = "deadhead"
        route = state["airline_list"]["Test Air"]["routes"]["AAA-BBB"]
        route["base_daily_demand"] = 150

        metrics = route_demand_metrics(state, {"AAA-BBB": route})

        self.assertEqual(metrics["AAA-BBB"]["assigned_seats"], 0)
        self.assertEqual(metrics["AAA-BBB"]["demand_left"], 150)


if __name__ == "__main__":
    unittest.main()
