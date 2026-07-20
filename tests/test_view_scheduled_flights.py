import unittest

from game.scheduling.view_flights import build_scheduled_flight_rows
from tests.test_daily_tick import make_state


class ViewScheduledFlightsTests(unittest.TestCase):
    def test_rows_follow_aircraft_rotation_in_numeric_time_order(self):
        state = make_state()
        aircraft = state["airline_list"]["Test Air"]["fleet"]["TEST-1"]
        aircraft["schedule"] = {
            "Fri": {
                "DVO-MNL": [
                    {
                        "start_time": "01:40",
                        "end_time": "02:50",
                        "start_airport": "DVO",
                        "end_airport": "MNL",
                    }
                ],
                "MNL-DVO": [
                    {
                        "start_time": "00:00",
                        "end_time": "01:10",
                        "start_airport": "MNL",
                        "end_airport": "DVO",
                    },
                    {
                        "start_time": "3:00",
                        "end_time": "04:10",
                        "start_airport": "MNL",
                        "end_airport": "DVO",
                    },
                ],
            },
            "Mon": {
                "AAA-BBB": [
                    {"start_time": "08:00", "end_time": "10:00"}
                ]
            },
        }

        rows = build_scheduled_flight_rows(state)

        self.assertEqual([row[0] for row in rows], ["Mon", "Fri", "Fri", "Fri"])
        friday_rows = [row for row in rows if row[0] == "Fri"]
        self.assertEqual(
            [row[4] for row in friday_rows], ["00:00", "01:40", "03:00"]
        )
        self.assertEqual([row[2] for row in friday_rows], [1, 2, 3])
        self.assertEqual(friday_rows[1][3], "DVO -> MNL")

    def test_deadhead_is_visible_in_rotation(self):
        state = make_state()
        block = state["airline_list"]["Test Air"]["fleet"]["TEST-1"][
            "schedule"
        ]["Mon"]["AAA-BBB"][0]
        block["service_type"] = "deadhead"

        rows = build_scheduled_flight_rows(state)

        self.assertEqual(rows[0][6], "Deadhead")


if __name__ == "__main__":
    unittest.main()
