"""Exact replay, transaction and presentation gates for explicit advancement."""
from copy import deepcopy
from datetime import timedelta
import tempfile
import unittest
from unittest.mock import patch

from app.session import Stage1Session
from game.aircraft_operations import fulfilment
from game.simulation import kernel
from game.simulation.pacing import RuntimeController, NANOSECOND
from game.world_state import validate_world
from game.world_state.timestamps import format_utc, parse_canonical_utc
from tests.profile_advancement import starting_world
from tests.profile_scheduling import copy_counts, digest


def historical_digest(world):
    """Keep fixed schema-7 witnesses; exclude only the additive empty foundation."""
    from tests.legacy_starter_fixture import strip_quarterly_foundation
    candidate = deepcopy(world)
    if candidate['metadata']['save_schema_version'] in (8, 9):
        strip_quarterly_foundation(candidate)
        candidate['metadata']['save_schema_version'] = 7
    return digest(candidate)


class AdvancementPerformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = starting_world(1)
        cls.asserted_input = 'fc4472f88f94593fae8f49f1b85640063d4ddf717415b737f2e550432934541e'

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.session = Stage1Session(save_root=self.temp.name, runtime_clock=lambda:0)
        self.session.world = deepcopy(self.base)
        self.session.career_id = self.session.save_store.new_career_id()

    def test_fast_forward_matches_baseline_hash_and_normal_speed_replay(self):
        schema8 = deepcopy(self.base)
        schema8['metadata']['save_schema_version'] = 8
        self.assertEqual(digest(schema8),
            'ce5c21ab5eaac8b0d364e1ab8520e248931e5a2dc61111b70d49353e99e1bc55')
        self.assertEqual(historical_digest(self.base), self.asserted_input)
        report = self.session.advance_seconds(2*86400)
        self.assertTrue(report.result.succeeded)
        self.assertEqual(historical_digest(self.session.world),
            '2aa62106a7fedd3425addc98841cc84273ab6fa0639a93bca5f4c764174df8b6')
        normal = deepcopy(self.base)
        kernel.configure_clock_ratios(normal,normal=30)
        # Equivalent initial clock configuration for the Normal Speed/explicit comparison;
        # the separate baseline witness above retains the original Normal ratio.
        self.session.world = deepcopy(normal)
        self.session.advance_seconds(2*86400)
        now = [0]
        runtime = RuntimeController(normal, clock=lambda:now[0])
        runtime.resume()
        now[0] = (2*86400*NANOSECOND+29)//30
        for _ in range(100):
            runtime.pump()
            if runtime.work is None and runtime.credit_ns < NANOSECOND:
                break
        else:
            self.fail('normal runtime did not reach target')
        self.assertFalse(runtime.blocked)
        runtime.pause()
        self.assertEqual(digest(normal), digest(self.session.world))
        self.session.save_manual()
        restored = Stage1Session(save_root=self.temp.name, runtime_clock=lambda:0)
        restored.load_saved(self.session.career_id)
        self.assertEqual(restored.authoritative_bytes(), self.session.authoritative_bytes())

    def test_booking_has_one_transaction_and_preserves_provider_isolation(self):
        with copy_counts() as copies, patch('game.simulation.kernel.validate_world',
                wraps=validate_world) as validations:
            report = self.session.advance_next_event()
        self.assertTrue(report.result.succeeded)
        self.assertEqual(report.event_rows[0]['event_type'], 'DAILY_BOOKING_CHECKPOINT')
        self.assertEqual(copies['world_copies'], 5)
        self.assertEqual(copies['fast_world_clones'], 5)
        self.assertEqual(validations.call_count, 2)

    def test_flight_handlers_use_enclosing_validation_and_two_world_copies(self):
        self.session.advance_next_event()  # Booking precedes the outbound.
        for expected in ('STAGE1_FLIGHT_DEPARTURE','STAGE1_FLIGHT_COMPLETION'):
            with copy_counts() as copies, patch.object(fulfilment, 'validate_world',
                    side_effect=AssertionError('nested validation')), patch(
                    'game.simulation.kernel.validate_world', wraps=validate_world) as validations:
                report = self.session.advance_next_event()
            self.assertTrue(report.result.succeeded)
            self.assertEqual(report.event_rows[0]['event_type'],expected)
            self.assertEqual(copies['world_copies'],2)
            self.assertEqual(validations.call_count,2)
        self.assertTrue(self.session.validate())

    def test_late_corrupt_completion_is_rejected_atomically_by_kernel(self):
        self.session.advance_next_event()
        self.session.advance_next_event()
        before = deepcopy(self.session.world)
        original = fulfilment._completion
        def corrupted(candidate,*args,**kwargs):
            result = original(candidate,*args,**kwargs)
            next(iter(candidate['world_state']['aircraft'].values()))['status']='BROKEN'
            return result
        with patch.object(fulfilment,'_completion',corrupted):
            report = self.session.advance_next_event()
        self.assertEqual(report.result.failure.code,'RESULT_VALIDATION_FAILED')
        self.assertEqual(self.session.world,before)

    def test_forged_event_token_does_not_skip_public_validation(self):
        world = deepcopy(self.base)
        next(iter(world['world_state']['aircraft'].values()))['status']='BROKEN'
        flight = next(iter(world['world_state']['dated_flights']))
        with patch.object(fulfilment,'validate_world',wraps=validate_world) as validation:
            result = fulfilment._departure(world,flight,resolve_event=False,_event_transaction=True)
        self.assertFalse(result.succeeded)
        validation.assert_called_once()

    def test_explicit_generation_budget_is_cumulative_and_bounded(self):
        self.session.new_game('CEO','Budget','MNL')
        world = self.session.world
        owner = world['world_state']['player']['primary_airline_id']
        due = format_utc(parse_canonical_utc(world['simulation']['time_utc'])+timedelta(seconds=1))
        def generate(context):
            for _ in range(3):
                context.schedule_event(event_type='NO_OP', due_at_utc=context.event['due_at_utc'],
                    owner_type='airline', owner_id=owner, operation_revision=0, priority=500,payload={})
        kernel.DEFAULT_EVENT_HANDLERS.register('TEST_ADVANCE_BATCH',generate)
        self.addCleanup(kernel.DEFAULT_EVENT_HANDLERS._handlers.pop,'TEST_ADVANCE_BATCH')
        kernel.schedule_event(world,event_type='TEST_ADVANCE_BATCH',due_at_utc=due,
            owner_type='airline',owner_id=owner,operation_revision=0,priority=500,payload={})
        with patch('app.session.DEFAULT_MAX_EVENTS_PER_ADVANCE',2):
            report = self.session.advance_seconds(2)
        self.assertEqual(report.result.failure.code,'EVENT_GENERATION_LIMIT_REACHED')
        self.assertEqual(len(report.result.completed_event_ids),1)
        self.assertEqual(world['simulation']['clock_state'],'PAUSED')
        self.assertTrue(self.session.validate())

    def test_utc_predicate_cache_preserves_original_syntax_and_bad_types(self):
        from game.world_state.timestamps import is_canonical_utc, _uncached_canonical_utc, _canonical_utc_text
        class UnhashableText(str):
            __hash__=None
        values = [None,{},[],1,True,'2026-09-07T00:00:00Z',
            '2026-09-07T00:00:00.000Z','0001-01-01T00:00:00Z','2026-02-30T00:00:00Z',
            UnhashableText('2026-09-07T00:00:00Z')]
        for value in values:
            self.assertEqual(is_canonical_utc(value),_uncached_canonical_utc(value))
        self.assertEqual(_canonical_utc_text.cache_info().maxsize,4096)

    def test_gui_fast_forward_batches_without_rebuilding_each_event(self):
        from app.gui.app import AirlineTycoonApp
        app = AirlineTycoonApp(session_factory=lambda:self.session)
        app.build()
        self.addCleanup(app.on_stop)
        self.addCleanup(app._dismiss)
        app._enter_game()
        # Use a real quiet new career; never invent a historical clock move.
        self.session.new_game('CEO','GUI batch','MNL')
        start = parse_canonical_utc(self.session.world['simulation']['time_utc'])
        owner = self.session.airline_id
        for i in range(1,71):
            kernel.schedule_event(self.session.world,event_type='NO_OP',due_at_utc=format_utc(start+timedelta(seconds=i)),
                owner_type='airline',owner_id=owner,operation_revision=0,priority=0,payload={})
        with patch.object(app,'_render_view', wraps=app._render_view) as render:
            app._begin_seconds(71)
            self.assertEqual(render.call_count,0)
            app.tick(0)
            self.assertTrue(self.session.advancing)
            self.assertEqual(render.call_count,0)
            for _ in range(100):
                app.tick(0)
                if not self.session.advancing:
                    break
            self.assertFalse(self.session.advancing)
            self.assertEqual(render.call_count,1)
        self.assertTrue(self.session.validate())

    def test_runtime_clone_is_exact_detached_and_keeps_compatibility_fallback(self):
        from game.world_state.serialization import _clone_runtime_world
        world = deepcopy(self.base)
        cloned = _clone_runtime_world(world)
        self.assertEqual(digest(cloned),digest(world))
        next(iter(cloned['world_state']['aircraft'].values()))['status']='BROKEN'
        self.assertEqual(historical_digest(world),self.asserted_input)
        payload = {'large':2**130,'fraction':-0.0,'unicode':'\u2603','flags':[True,None,False]}
        self.assertEqual(_clone_runtime_world(payload),payload)
        import math
        self.assertEqual(math.copysign(1, _clone_runtime_world(payload)['fraction']), -1)
        self.assertEqual(list(_clone_runtime_world(payload)), list(payload))
        shared = [1, 2]
        aliased = _clone_runtime_world({'a': shared, 'b': shared})
        self.assertIs(aliased['a'], aliased['b'])
        self.assertIsNot(aliased['a'], shared)
        class CompatibleKey(str):
            pass
        # Non-plain compatibility shape uses the previous deepcopy path.
        custom = {CompatibleKey('name'): [1,2]}
        self.assertEqual(_clone_runtime_world(custom),custom)

    def test_validator_reuses_only_successful_whole_envelope_json_proof(self):
        import game.world_state.validation as validation
        with patch.object(validation,'_plain_authority_tree',wraps=validation._plain_authority_tree) as graph, patch.object(validation,'json_compatibility_error',wraps=validation.json_compatibility_error) as scans:
            self.assertTrue(validate_world(self.base).is_valid)
            self.assertEqual(graph.call_count,1)
            self.assertEqual(scans.call_count,0)  # The exact combined graph proof succeeded.
        bad=deepcopy(self.base)
        event=next(iter(bad['world_state']['pending_events'].values()))
        event['payload']['bad']=object()
        result=validate_world(bad)
        self.assertFalse(result.is_valid)
        self.assertTrue(any(issue.code=='not_json_compatible' for issue in result.errors))

    def test_validation_still_rejects_aliases(self):
        bad=deepcopy(self.base)
        events=list(bad['world_state']['pending_events'].values())
        events[1]['payload']=events[0]['payload']
        result=validate_world(bad)
        self.assertFalse(result.is_valid)
        self.assertTrue(any('alias' in issue.code or 'alias' in issue.message for issue in result.errors))

    def test_long_target_in_quiet_career_processes_all_ninety_daily_checkpoints(self):
        self.session.new_game('CEO','Long target','MNL')
        initial=len(self.session.world['world_state']['booking_state']['booking_checkpoints'])
        target=format_utc(parse_canonical_utc(self.session.world['simulation']['time_utc'])+timedelta(days=90))
        report=self.session.advance_to(target)
        self.assertTrue(report.result.succeeded)
        self.assertEqual(self.session.world['simulation']['time_utc'],target)
        state=self.session.world['world_state']
        self.assertEqual(len(state['booking_state']['booking_checkpoints'])-initial,90)
        self.assertTrue(self.session.validate())
        self.assertEqual(self.session.world['simulation']['clock_state'],'PAUSED')

    def test_field_scan_keeps_nested_leaf_checks_and_exact_issue_order(self):
        from game.world_state.validation import _Validator
        validator=_Validator({})
        validator.world={'history':{'operations':[1,None,{'amount_minor':1.5,
            'nested':[True,{'origin_iata':'MNL','at_utc':'bad'}]}]}}
        validator.validate_no_name_references_or_float_money()
        self.assertEqual([(e.code,e.path) for e in validator.errors],[
            ('invalid_money','$.world_state.history.operations[2].amount_minor'),
            ('name_based_authoritative_reference','$.world_state.history.operations[2].nested[1].origin_iata'),
            ('invalid_timestamp','$.world_state.history.operations[2].nested[1].at_utc')])
