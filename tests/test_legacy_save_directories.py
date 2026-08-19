import json
import os
import tempfile
import unittest
from unittest.mock import patch

from game import game_state as legacy_state
from game.new_game import load_game_menu


def make_legacy_state():
    state = legacy_state.default_game_state()
    state["player_info"].update(
        {
            "ceo_name": "Fresh Clone CEO",
            "airline_name": "Directory Air",
            "current_focus": "Directory Air",
        }
    )
    state["airline_list"]["Directory Air"] = {
        "hubs": {},
        "routes": {},
        "fleet": {},
        "finances": {"cash_on_hand": 1000},
    }
    return state


class LegacySaveDirectoryTests(unittest.TestCase):
    def test_absent_save_directory_is_created_and_listed_as_empty(self):
        with tempfile.TemporaryDirectory() as temporary_root:
            save_dir = os.path.join(temporary_root, "Saves")
            with patch.object(legacy_state, "SAVE_DIRECTORY", save_dir):
                self.assertEqual(legacy_state.list_save_files(), [])

            self.assertTrue(os.path.isdir(save_dir))

    def test_load_game_menu_handles_fresh_clone_without_save_directory(self):
        with tempfile.TemporaryDirectory() as temporary_root:
            save_dir = os.path.join(temporary_root, "Saves")
            with (
                patch.object(legacy_state, "SAVE_DIRECTORY", save_dir),
                patch("builtins.input", return_value=""),
                patch("builtins.print"),
                patch("game.new_game.game_loop") as mocked_game_loop,
            ):
                load_game_menu()

            self.assertTrue(os.path.isdir(save_dir))
            mocked_game_loop.assert_not_called()

    def test_autosave_creates_missing_save_directory_before_writing(self):
        state = make_legacy_state()
        with tempfile.TemporaryDirectory() as temporary_root:
            save_dir = os.path.join(temporary_root, "Saves")
            with (
                patch.object(legacy_state, "SAVE_DIRECTORY", save_dir),
                patch.object(legacy_state, "game_state", state),
                patch("builtins.print"),
            ):
                legacy_state.autosave()

            filenames = os.listdir(save_dir)
            self.assertEqual(len(filenames), 1)
            self.assertRegex(
                filenames[0],
                r"^Fresh_Clone_CEO_Directory_Air_autosave_\d{8}_\d{6}\.json$",
            )
            with open(os.path.join(save_dir, filenames[0]), encoding="utf-8") as save_file:
                self.assertEqual(json.load(save_file), state)

    def test_manual_save_and_missing_load_use_configured_save_directory(self):
        state = make_legacy_state()
        with tempfile.TemporaryDirectory() as temporary_root:
            save_dir = os.path.join(temporary_root, "Saves")
            with (
                patch.object(legacy_state, "SAVE_DIRECTORY", save_dir),
                patch.object(legacy_state, "game_state", state),
                patch.object(legacy_state, "last_saved_filename", None),
                patch("builtins.print"),
            ):
                legacy_state.save_game(state, is_new=True)
                saved_files = legacy_state.list_save_files()
                self.assertEqual(len(saved_files), 1)

                os.remove(os.path.join(save_dir, saved_files[0]))
                legacy_state.load_game("missing.json")

            self.assertTrue(os.path.isdir(save_dir))


if __name__ == "__main__":
    unittest.main()
