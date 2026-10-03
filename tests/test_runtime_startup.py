"""Fresh-process runtime startup/load regressions; no real career files."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


REQUIRED_EVENTS = {
    'NO_OP', 'STAGE1_FLIGHT_DEPARTURE', 'STAGE1_FLIGHT_COMPLETION',
    'DAILY_BOOKING_CHECKPOINT', 'AIRCRAFT_MARKET_ROTATION',
    'AIRCRAFT_CONTRACT_PAYMENT', 'AIRCRAFT_CONTRACT_EXPIRY',
    'STAGE1_WEEKLY_PUBLICATION',
}

WORKER = r"""
import hashlib, json, sys
from datetime import timedelta
from app.session import Stage1Session
from game.simulation.kernel import DEFAULT_EVENT_HANDLERS
from game.world_state.timestamps import format_utc, parse_canonical_utc
assert 'app.gui.app' not in sys.modules
assert 'game.booking.checkpoint' not in sys.modules, 'fresh import state was concealed'
root, career, mode = sys.argv[1:]
if mode == 'reference':
    import game.booking.checkpoint
session = Stage1Session(save_root=root, runtime_clock=lambda: 0)
required = {
    'NO_OP', 'STAGE1_FLIGHT_DEPARTURE', 'STAGE1_FLIGHT_COMPLETION',
    'DAILY_BOOKING_CHECKPOINT', 'AIRCRAFT_MARKET_ROTATION',
    'AIRCRAFT_CONTRACT_PAYMENT', 'AIRCRAFT_CONTRACT_EXPIRY',
    'STAGE1_WEEKLY_PUBLICATION'}
assert set(DEFAULT_EVENT_HANDLERS._handlers) == required
before_handlers = dict(DEFAULT_EVENT_HANDLERS._handlers)
if mode == 'new':
    session.new_game('CEO', 'Startup Air', 'MNL')
else:
    session.new_game = lambda *a, **k: (_ for _ in ()).throw(AssertionError('New Game forbidden'))
    session.load_saved(career)
assert session.world['simulation']['clock_state'] == 'PAUSED'
assert dict(DEFAULT_EVENT_HANDLERS._handlers) == before_handlers
world = session.world['world_state']
event = min((e for e in world['pending_events'].values()
             if e['event_type'] == 'DAILY_BOOKING_CHECKPOINT'), key=lambda e:e['due_at_utc'])
target = format_utc(parse_canonical_utc(event['due_at_utc']) + timedelta(seconds=1))
report = session.advance_to(target)
assert report.result.failure is None, report.result.failure
assert session.world['simulation']['time_utc'] == target
world = session.world['world_state']
assert world['event_history'][event['event_id']]['status'] == 'COMPLETED'
assert event['event_id'] in report.result.completed_event_ids
checkpoints = world['booking_state']['booking_checkpoints']
assert any(c['checkpoint_date'] == event['payload']['checkpoint_date']
           and c['status'] == 'COMPLETED' for c in checkpoints.values())
assert sum(e['event_type'] == 'DAILY_BOOKING_CHECKPOINT'
           for e in world['pending_events'].values()) == 1
records = [world['event_history'][key] for key in report.result.completed_event_ids]
keys = [(e['due_at_utc'], *e['order_key'], e['event_id']) for e in records]
assert keys == sorted(keys)
assert session.validate()
state = session.authoritative_bytes()
session.save_manual()
restored = Stage1Session(save_root=root, runtime_clock=lambda: 0)
restored.load_saved(session.career_id)
assert restored.validate() and restored.authoritative_bytes() == state
assert restored.world['simulation']['clock_state'] == 'PAUSED'
print(json.dumps({'sha256':hashlib.sha256(state).hexdigest(),
                  'events':report.result.completed_event_ids,
                  'bookings':len(world['bookings']), 'handlers':sorted(required)}))
"""


class RuntimeStartupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.session import Stage1Session
        from game.scheduling import WeeklyDraft
        cls.fixture = tempfile.TemporaryDirectory()
        session = Stage1Session(save_root=cls.fixture.name, runtime_clock=lambda: 0)
        session.new_game('CEO', 'Startup Air', 'MNL')
        state = session.world['world_state']
        ports = {row['reference_code']: key for key,row in state['airports'].items()}
        draft = WeeklyDraft(session.world, airline_id=session.airline_id,
                            aircraft_id=next(iter(state['aircraft'])))
        draft.add_weekdays(ports['MNL'], ports['DVO'], ('2026-09-07',), '08:00',
                          return_flight=True, fare_minor=11600)
        draft.save_current(session.world)
        session.save_manual()
        cls.career = session.career_id

    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup()

    def worker(self, mode):
        with tempfile.TemporaryDirectory() as root:
            shutil.copytree(self.fixture.name, root, dirs_exist_ok=True)
            result = subprocess.run([sys.executable, '-B', '-c', WORKER, root,
                                     self.career, mode], cwd=Path(__file__).resolve().parents[1],
                                    capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return json.loads(result.stdout)

    def test_fresh_load_executes_booking_and_matches_explicit_import_reference(self):
        normal = self.worker('load')
        self.assertEqual(normal, self.worker('reference'))
        self.assertEqual(set(normal['handlers']), REQUIRED_EVENTS)

    def test_fresh_new_game_has_same_complete_handlers_and_processes_booking(self):
        self.assertEqual(set(self.worker('new')['handlers']), REQUIRED_EVENTS)

    def test_standalone_runtime_initialization_is_complete_and_idempotent(self):
        code = r"""
from game.simulation.kernel import DEFAULT_EVENT_HANDLERS, EventHandlerRegistry
from game.simulation.pacing import RuntimeController
from game.simulation.handlers import initialize_runtime_handlers
assert 'DAILY_BOOKING_CHECKPOINT' not in DEFAULT_EVENT_HANDLERS._handlers
world = {'simulation': {'clock_state':'PAUSED'}}
custom = EventHandlerRegistry()
RuntimeController(world, registry=custom, clock=lambda:0)
assert custom._handlers == {}
RuntimeController(world, clock=lambda:0)
expected = dict(DEFAULT_EVENT_HANDLERS._handlers)
assert len(expected) == 8 and 'DAILY_BOOKING_CHECKPOINT' in expected
assert initialize_runtime_handlers() is DEFAULT_EVENT_HANDLERS
assert DEFAULT_EVENT_HANDLERS._handlers == expected
DEFAULT_EVENT_HANDLERS._handlers.clear()
initialize_runtime_handlers()
assert DEFAULT_EVENT_HANDLERS._handlers == expected
DEFAULT_EVENT_HANDLERS._handlers['NO_OP'] = lambda context:None
try:
    initialize_runtime_handlers()
except ValueError:
    pass
else:
    raise AssertionError('conflicting handler silently replaced')
"""
        result = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True,
                                text=True, timeout=90)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_complete_handler_manifest_matches_all_domain_registrations(self):
        # Inventory actual registrations so a new domain handler cannot quietly
        # remain outside the shared startup manifest.
        import ast
        import importlib
        from game.simulation.handlers import initialize_runtime_handlers
        registry = initialize_runtime_handlers()
        discovered = set()
        root = Path(__file__).resolve().parents[1]
        for path in (root / 'game').rglob('*.py'):
            tree = ast.parse(path.read_text(encoding='utf-8'))
            registrations = [node for node in ast.walk(tree)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == 'DEFAULT_EVENT_HANDLERS'
                and node.func.attr == 'register']
            if not registrations:
                continue
            module = importlib.import_module('.'.join(path.relative_to(root).with_suffix('').parts))
            for call in registrations:
                arg = call.args[0]
                event_type = arg.value if isinstance(arg, ast.Constant) else getattr(module, arg.id)
                discovered.add(event_type)
                self.assertIsNotNone(registry.handler_for(event_type))
        self.assertEqual(discovered, REQUIRED_EVENTS)
