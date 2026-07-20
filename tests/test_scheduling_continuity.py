import unittest

from game.scheduling.validators import validate_aircraft_continuity


class SchedulingContinuityTests(unittest.TestCase):
    def setUp(self):
        self.schedule = [
            {
                "start_time": "06:00",
                "end_time": "07:10",
                "start_airport": "MNL",
                "end_airport": "DVO",
            }
        ]

    def test_connecting_flight_can_depart_previous_destination(self):
        valid, reason = validate_aircraft_continuity(
            self.schedule, 460, 580, "DVO", "CEB", "MNL"
        )
        self.assertTrue(valid, reason)

    def test_aircraft_cannot_teleport_back_to_hub(self):
        valid, reason = validate_aircraft_continuity(
            self.schedule, 460, 580, "MNL", "CEB", "MNL"
        )
        self.assertFalse(valid)
        self.assertIn("DVO", reason)

    def test_inserted_flight_must_connect_to_following_flight(self):
        schedule = self.schedule + [
            {
                "start_time": "10:00",
                "end_time": "11:00",
                "start_airport": "MNL",
                "end_airport": "CEB",
            }
        ]
        valid, reason = validate_aircraft_continuity(
            schedule, 460, 580, "DVO", "ILO", "MNL"
        )
        self.assertFalse(valid)
        self.assertIn("MNL", reason)


if __name__ == "__main__":
    unittest.main()
