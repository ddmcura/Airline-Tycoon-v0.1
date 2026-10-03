"""Validated, in-memory payment fixtures; setup is outside benchmark timing."""
from datetime import timedelta

from game.aircraft_market.step5 import accept_lease, preview_lease
from game.simulation import kernel
from game.simulation.handlers import initialize_runtime_handlers
from game.world_state import create_stage1_new_game, validate_world
from game.world_state.timestamps import format_utc, parse_canonical_utc


def payment_world(count=1, *, near=False, history=0, final=False, lead_seconds=1):
    initialize_runtime_handlers()
    world = create_stage1_new_game(scenario_id='stage1-philippines-v1',
        ceo_display_name='Payment CEO', airline_display_name='Payment Proof Air',
        base_airport_reference_code='MNL')
    # Use real clock commands; anniversaries avoid the midnight causal fences.
    assert kernel.process_events_through(world, '2026-09-01T00:00:01Z').succeeded
    state = world['world_state']
    airline = state['player']['primary_airline_id']
    base = state['airlines'][airline]['base_airport_ids'][0]
    offer = state['aircraft_market_state']['active_lease_offer_ids'][0]
    # Synthetic inventory quantity is canonical and local to this fixture.
    state['aircraft_lease_offers'][offer]['available_quantity'] = count + 1
    for index in range(count):
        if near and index:
            now = parse_canonical_utc(world['simulation']['time_utc'])
            assert kernel.process_events_through(world, format_utc(now + timedelta(seconds=1))).succeeded
        accept_lease(world, preview_lease(world, airline_id=airline, offer_id=offer,
            contract_type='OPERATING_LEASE' if index % 2 else 'LEASE_TO_OWN',
            term_years=1, delivery_airport_id=base, command_id=f'payment-fixture-{index}'))
    contracts = world['world_state']['aircraft_contracts']
    target = max(row['expires_at_utc'] if final else row['next_payment_at_utc']
                 for row in contracts.values())
    first = min(row['expires_at_utc'] if final else row['next_payment_at_utc']
                for row in contracts.values())
    before = format_utc(parse_canonical_utc(first) - timedelta(seconds=lead_seconds))
    result = kernel.process_events_through(world, before, max_generated_events=10000)
    assert result.succeeded, result.failure
    now = world['simulation']['time_utc']
    for _ in range(history):
        kernel.schedule_event(world, event_type='NO_OP', due_at_utc=now,
                              owner_type='airline', owner_id=airline)
    if history:
        assert kernel.process_events_through(world, now).succeeded
    assert validate_world(world).is_valid
    return world, target
