import unittest

from game.scheduling.suggest import next_available_after, suggest_available_slots


class SchedulingSuggestionTests(unittest.TestCase):
    def test_suggestions_prioritize_after_existing_schedule(self):
        existing = [{"start_time": "07:00", "end_time": "08:40"}]

        suggestions = suggest_available_slots(existing, 60)

        self.assertEqual(suggestions[0], "08:40")
        self.assertIn("00:00", suggestions)

    def test_conflict_moves_to_end_of_interfering_flight(self):
        existing = [{"start_time": "07:00", "end_time": "08:40"}]

        suggestion = next_available_after(existing, 480, 60)

        self.assertEqual(suggestion, 520)

    def test_conflict_can_move_across_multiple_flights(self):
        existing = [
            {"start_time": "07:00", "end_time": "08:40"},
            {"start_time": "09:00", "end_time": "10:30"},
        ]

        suggestion = next_available_after(existing, 480, 60)

        self.assertEqual(suggestion, 630)


if __name__ == "__main__":
    unittest.main()
