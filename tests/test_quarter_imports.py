"""Fresh interpreter coverage for quarter imports and canonical calendar behavior."""
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest


class QuarterImportTests(unittest.TestCase):
    def test_fresh_import_orders_and_helpers(self):
        checks = textwrap.dedent('''
            from datetime import date, datetime, timedelta, timezone
            from game.utils.quarters import (
                Quarter, _utc_date, normal_target_quarter,
                parse_quarter_id, quarter_containing,
            )
            import unittest
            case = unittest.TestCase()
            case.assertEqual(_utc_date('2028-02-29T23:59:59Z'), date(2028, 2, 29))
            case.assertEqual(_utc_date('2028-02-29'), date(2028, 2, 29))
            case.assertEqual(quarter_containing(date(2028, 2, 29)), Quarter(2028, 1))
            case.assertEqual(normal_target_quarter('2028-03-31T23:59:59Z'), Quarter(2028, 3))
            local = datetime(2028, 4, 1, tzinfo=timezone(timedelta(hours=8)))
            case.assertEqual(_utc_date(local), date(2028, 3, 31))
            for number in range(1, 5):
                quarter = Quarter(2028, number)
                case.assertEqual(parse_quarter_id(quarter.quarter_id), quarter)
                case.assertEqual(quarter_containing(quarter.start_utc), quarter)
                case.assertEqual(quarter_containing(quarter.end_exclusive_utc - timedelta(seconds=1)), quarter)
                case.assertEqual(quarter_containing(quarter.end_exclusive_utc), quarter.shift())
            def rejects(call, value, message):
                try:
                    call(value)
                except Exception as exc:
                    case.assertIs(type(exc), ValueError)
                    case.assertEqual(str(exc), message)
                else:
                    case.fail('expected ValueError for ' + repr(value))
            for value in ('invalid', '2028-02-30T00:00:00Z',
                          '2028-01-01T00:00:00+00:00', '2028-01-01T00:00:00',
                          '2028-01-01T00:00:00.000Z', '2028-01-01T00:00:00.001Z'):
                for helper in (_utc_date, quarter_containing, normal_target_quarter):
                    rejects(helper, value, 'timestamp must be canonical UTC YYYY-MM-DDTHH:MM:SSZ')
            for value in (datetime(2028, 1, 1),
                          datetime(2028, 1, 1, microsecond=1, tzinfo=timezone.utc)):
                for helper in (_utc_date, quarter_containing, normal_target_quarter):
                    rejects(helper, value, 'quarter timestamps must be aware whole seconds')
            for value in ('2028-Q0', '2028-Q5', '28-Q1', '2028-q1', None, True):
                rejects(parse_quarter_id, value, 'quarter identity must be YYYY-Q1..YYYY-Q4')
            rejects(parse_quarter_id, '0000-Q1', 'quarter year must be 1..9999')
            rejects(_utc_date, True, 'quarter input must be a UTC timestamp or calendar date')
        ''')
        for first in ('game.utils.quarters', 'game.world_state', 'app.session'):
            with self.subTest(first=first):
                result = subprocess.run(
                    [sys.executable, '-B', '-c', 'import ' + first + '\n' + checks],
                    cwd=Path(__file__).resolve().parents[1],
                    capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
