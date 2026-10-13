"""Both provider invocations must remain detached from the discovery caller."""
from copy import deepcopy
import unittest
from unittest.mock import patch

import game.world_state  # Keep the known utilities-first import issue separate.
from game.booking import shopping
from game.demand import activation
from game.scheduling import quarterly_supply
from tests import test_quarterly_backend as fixtures


class QuarterlyProviderIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = fixtures.QuarterlyBackendTests.fixture()[0]

    def setUp(self):
        self.world = deepcopy(self.base)
        self.before = fixtures.encoded(self.world)

    def discover(self, provider=None):
        return activation.discover_active_market_ids(self.world,
            providers=(shopping._IsolatedActivationProvider(
                provider or quarterly_supply.QuarterlyActivationProvider()),),
            require_model4_pack_authority=True)

    def assert_unchanged(self):
        self.assertEqual(fixtures.encoded(self.world), self.before)

    def test_normal_discovery_keeps_mutable_copies_detached(self):
        copied = []
        def capture(value, *args, **kwargs):
            result = deepcopy(value, *args, **kwargs)
            if type(value) is dict and 'metadata' in value and 'world_state' in value:
                copied.append((value, result))
            return result
        with patch.object(shopping, 'deepcopy', capture), patch.object(activation, 'deepcopy', capture):
            self.assertTrue(self.discover())
        self.assertTrue(copied)
        for source, result in copied:
            self.assertIsNot(source, result)
            self.assertIsNot(source['world_state'], result['world_state'])
            self.assertIsNot(source['world_state']['airports'], result['world_state']['airports'])
        self.assert_unchanged()

    def presence_probe(self, invocation, action):
        original = quarterly_supply._published_market_presence
        observed = []
        def probe(supply):
            observed.append(supply.envelope)
            if len(observed) == invocation:
                action(supply.envelope)
            return original(supply)
        return probe, observed

    def test_primary_nested_mutation_preserves_diagnostic_and_caller(self):
        probe, observed = self.presence_probe(1,
            lambda world: world['metadata'].update(isolation_sentinel='primary'))
        with patch.object(quarterly_supply, '_published_market_presence', probe):
            with self.assertRaisesRegex(ValueError,
                    'invalid activation provider result: activation provider mutated its detached input'):
                self.discover()
        self.assertIsNot(observed[0], self.world)
        self.assert_unchanged()

    def test_secondary_nested_mutation_preserves_diagnostic_and_caller(self):
        probe, observed = self.presence_probe(2,
            lambda world: world['metadata'].update(isolation_sentinel='secondary'))
        with patch.object(quarterly_supply, '_published_market_presence', probe):
            with self.assertRaisesRegex(ValueError,
                    'invalid activation provider result: activation provider mutated its detached state'):
                self.discover()
        self.assertGreaterEqual(len(observed), 2)
        self.assertIsNot(observed[0], observed[1])
        self.assertIsNot(observed[1], self.world)
        self.assert_unchanged()

    def test_secondary_exception_after_mutation_preserves_caller_and_retry(self):
        def interrupt(world):
            world['metadata']['isolation_sentinel'] = 'partial'
            raise RuntimeError('secondary interrupted')
        probe, observed = self.presence_probe(2, interrupt)
        with patch.object(quarterly_supply, '_published_market_presence', probe):
            with self.assertRaisesRegex(ValueError, 'invalid activation provider result: secondary interrupted'):
                self.discover()
        self.assert_unchanged()
        control = self.discover()
        self.assertTrue(control)
        self.assert_unchanged()

    def test_secondary_retained_reference_cannot_mutate_caller_after_return(self):
        probe, observed = self.presence_probe(2, lambda world: None)
        with patch.object(quarterly_supply, '_published_market_presence', probe):
            result = self.discover()
        self.assertTrue(result)
        # Pack eligibility can perform another read after the guarded adapter.
        self.assertGreaterEqual(len(observed), 2)
        self.assertIsNot(observed[1], self.world)
        observed[1]['metadata']['isolation_sentinel'] = 'after return'
        self.assert_unchanged()

    def test_secondary_exception_before_output_preserves_caller(self):
        def interrupt(world):
            raise RuntimeError('no output')
        probe, _ = self.presence_probe(2, interrupt)
        with patch.object(quarterly_supply, '_published_market_presence', probe):
            with self.assertRaisesRegex(ValueError, 'invalid activation provider result: no output'):
                self.discover()
        self.assert_unchanged()

    def test_invalid_output_rejects_without_changing_caller(self):
        class Invalid(quarterly_supply.QuarterlyActivationProvider):
            def active_market_ids(self, *args, **kwargs):
                return [None]
        with self.assertRaisesRegex(ValueError, 'activation provider returned a non-string market ID'):
            self.discover(Invalid())
        self.assert_unchanged()

    def test_mutable_output_is_detached_and_cannot_change_caller(self):
        markets = list(quarterly_supply.QuarterlyActivationProvider().active_market_ids(
            self.world, activation.ActivationWindow(self.world['simulation']['time_utc'],
                '2028-01-01T00:00:00Z')))
        class Mutable(quarterly_supply.QuarterlyActivationProvider):
            def active_market_ids(self, *args, **kwargs):
                return markets
        result = self.discover(Mutable())
        markets.clear()
        self.assertTrue(result)
        self.assert_unchanged()


if __name__ == '__main__':
    unittest.main()
