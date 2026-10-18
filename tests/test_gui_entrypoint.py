"""GUI startup forwards supported options before Kivy argument parsing."""
import runpy
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch


class GuiEntrypointTests(unittest.TestCase):
    def test_startup_with_default_closed_and_quarterly_options(self):
        for flags, quarterly, closed in (
            ([], False, False),
            (['--closed-owner'], False, True),
            (['--closed-owner', '--quarterly-dev'], True, True),
        ):
            with self.subTest(flags=flags):
                app = ModuleType('app.gui.app')
                app.main = Mock(return_value=0)
                with patch.dict(sys.modules, {'app.gui.app': app}), patch.object(
                        sys, 'argv', ['app.gui', *flags]):
                    with self.assertRaises(SystemExit) as stopped:
                        runpy.run_module('app.gui', run_name='__main__')
                    self.assertEqual(stopped.exception.code, 0)
                    self.assertEqual(sys.argv, ['app.gui'])
                app.main.assert_called_once_with(
                    quarterly_development=quarterly, closed_owner=closed)


if __name__ == '__main__':
    unittest.main()
