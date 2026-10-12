"""Published presence equivalence and disposable activation-owner lifetime."""
from copy import deepcopy
from datetime import timedelta
import gc
import unittest
import weakref
from unittest.mock import patch

from game.demand import activation
from game.scheduling import quarterly_supply
from game.simulation.resolver import resolve_until
from game.world_state.quarterly_construction import retire_service
from game.world_state.timestamps import parse_canonical_utc, format_utc
from tests import test_quarterly_backend as fixtures


class QuarterlyActivationPresenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = fixtures.QuarterlyBackendTests.fixture()[0]

    def setUp(self):
        self.world = deepcopy(self.base)

    def window(self):
        start = self.world['simulation']['time_utc']
        return activation.ActivationWindow(start,
            format_utc(parse_canonical_utc(start) + timedelta(days=365)))

    def test_presence_matches_index_without_allocating_shopping_owner(self):
        expected = tuple(sorted(quarterly_supply.QuarterlyShoppingIndexes(self.world).by_market))
        before = fixtures.encoded(self.world)
        with patch.object(quarterly_supply, 'QuarterlyShoppingIndexes',
                side_effect=AssertionError('activation must not retain a shopping owner')):
            actual = quarterly_supply.QuarterlyActivationProvider().active_market_ids(self.world, self.window())
            direct = activation.DirectPublishedServiceActivationProvider().active_market_ids(self.world, self.window())
        self.assertEqual(actual, expected)
        self.assertEqual(direct, expected)
        self.assertEqual(fixtures.encoded(self.world), before)

    def test_activation_supply_releases_without_waiting_for_cyclic_gc(self):
        references = []
        original = quarterly_supply.QuarterlySupply.__init__
        def capture(supply, *args, **kwargs):
            original(supply, *args, **kwargs)
            references.append(weakref.ref(supply))
        enabled = gc.isenabled()
        gc.disable()
        try:
            with patch.object(quarterly_supply.QuarterlySupply, '__init__', capture):
                self.assertTrue(quarterly_supply.QuarterlyActivationProvider().active_market_ids(self.world, self.window()))
            self.assertTrue(references)
            self.assertTrue(all(reference() is None for reference in references))
        finally:
            if enabled:
                gc.enable()

    def test_retirement_and_unpublished_sources_are_observed_fresh(self):
        provider = quarterly_supply.QuarterlyActivationProvider()
        original = provider.active_market_ids(self.world, self.window())
        service = next(iter(self.world['world_state']['services']))
        retire_service(self.world, service)
        current = provider.active_market_ids(self.world, self.window())
        self.assertLess(len(current), len(original))
        self.assertEqual(current, tuple(sorted(quarterly_supply.QuarterlyShoppingIndexes(self.world).by_market)))
        draft = fixtures.QuarterlyBackendTests.fixture(quarter='2027-Q2', published=False)[0]
        self.assertEqual(provider.active_market_ids(draft, self.window()), ())

    def test_complete_strict_shared_and_original_activation_worlds_match(self):
        target = '2027-01-02T15:00:00Z'
        reference = deepcopy(self.world)
        def original_activation(provider, envelope, window, **kwargs):
            return tuple(sorted(quarterly_supply.QuarterlyShoppingIndexes(envelope).by_market))
        with patch.object(quarterly_supply.QuarterlyActivationProvider, 'active_market_ids', original_activation):
            expected = resolve_until(reference, target, shared=False)
        self.assertTrue(expected.succeeded, expected)
        for shared, cap in ((False, 1), (True, 1), (True, 2), (True, 8)):
            with self.subTest(shared=shared, cap=cap):
                candidate = deepcopy(self.world)
                actual = resolve_until(candidate, target, shared=shared, max_batch_events=cap)
                self.assertEqual(actual, expected)
                self.assertEqual(fixtures.encoded(candidate), fixtures.encoded(reference))


if __name__ == '__main__': unittest.main()
