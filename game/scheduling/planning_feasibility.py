"""Transient chronological feasibility; never a movement/publication command."""
from datetime import timedelta
from game.world_state.timestamps import parse_canonical_utc
from .activation import initial_week_window
from .timing import timing_bounds


class PlanningFeasibility:
    """Operation-local travel inputs; retained real obligations remain in the chain."""
    def __init__(self, draft):
        self.draft = draft
        self.envelope = draft._base
        self.world = self.envelope['world_state']
        self.now = parse_canonical_utc(self.envelope['simulation']['time_utc'])
        self.minimum = self.envelope['simulation']['configuration']['scheduling']['minimum_turnaround_seconds']
        self.travel = {}

    def bounds(self, origin, destination):
        key = (origin, destination)
        if key not in self.travel:
            self.travel[key] = timing_bounds(self.draft._snapshot(origin, destination))[1]
        return self.travel[key]

    def ready(self, previous, origin, preparation):
        """Earliest off-block, using the same reservation/turnaround inequalities.

        V2 reserves turnaround BEFORE each movement, post=0. V1 retains its
        post+pre handling. Minimum turnaround is a max constraint, never added
        a second time to the same boundary. No aircraft state is changed.
        """
        aircraft = self.world['aircraft'][self.draft.aircraft_id]
        location = previous[5] if previous else aircraft['current_airport_id']
        end = previous[1] if previous else self.now
        arrival = previous[3] if previous else None
        if location == origin:
            return max(end + timedelta(seconds=preparation),
                       arrival + timedelta(seconds=self.minimum) if arrival else self.now)
        pre, block, post = self.bounds(location, origin)
        departure = max(end + timedelta(seconds=pre),
                        arrival + timedelta(seconds=self.minimum) if arrival else self.now)
        reposition_arrival = departure + timedelta(seconds=block)
        return max(reposition_arrival + timedelta(seconds=post + preparation),
                   reposition_arrival + timedelta(seconds=self.minimum))

    def conflict(self, previous, row):
        start, end, departure, arrival, origin, destination = row
        preparation = int((departure-start).total_seconds())
        location = previous[5] if previous else self.world['aircraft'][self.draft.aircraft_id]['current_airport_id']
        try:
            ready = self.ready(previous, origin, preparation)
        except (ValueError, KeyError) as exc:
            return ValueError(f'REPOSITIONING_INFEASIBLE: aircraft {self.draft.aircraft_id} cannot reposition {self.code(location)} → {self.code(origin)}: {exc}')
        if previous is not None and start < previous[1]:
            return ValueError(f'AIRCRAFT_OVERLAP: aircraft {self.draft.aircraft_id} reserved ground/flight blocks overlap at {departure.isoformat()}')
        if departure >= ready:
            return None
        if location == origin:
            return ValueError('INSUFFICIENT_TURNAROUND: reserved ground/flight blocks overlap or readiness is unavailable')
        gap = int((departure-(previous[3] if previous else self.now)).total_seconds())
        return ValueError(f'REPOSITIONING_INFEASIBLE: aircraft {self.draft.aircraft_id} cannot reposition {self.code(location)} → {self.code(origin)} in time; gap {gap}s, earliest ready {ready.isoformat()}, requested {departure.isoformat()}')

    def code(self, airport):
        return self.world['airports'][airport]['reference_code']

    def validate(self, rows, eligible, week_end):
        """Past intent is inert. Only the initial infeasible prefix may skip.

        Published rows are never eligible for skipping. Feasible draft movement
        starts strict chronological feasibility, including every later adjacency.
        Existing publication retains literal continuity independently.
        """
        beginning, boundary = initial_week_window(self.envelope, self.draft.aircraft_id)
        from .recurrence import POLICY
        established = []
        for flight in self.world['dated_flights'].values():
            if flight['planned_aircraft_id'] != self.draft.aircraft_id or flight['status'] in {'SUPERSEDED','CANCELLED'}:
                continue
            revision = self.world['schedule_definitions'][flight['schedule_id']]['revisions'][str(flight['schedule_revision'])]
            departure = parse_canonical_utc(flight['scheduled_off_block_utc'])
            if revision['recurrence'].get('publication_policy') == POLICY and beginning <= departure < boundary:
                established.append(departure)
        activated_at = min(established) if established else None
        activated = activated_at is not None and activated_at <= self.now
        ordered = sorted(rows)
        protected = [r for r in ordered if r not in eligible and r[2] >= self.now]
        previous = None
        result = []
        for row in ordered:
            if row in eligible and row[0] < self.now:
                continue
            if row[2] < self.now:
                # Actual history/active work supplies readiness, never past intent.
                if row not in eligible and (row[1] > self.now or row[3] + timedelta(seconds=self.minimum) > self.now):
                    previous = row
                continue
            can_skip = (not activated and week_end is not None and row[2] < week_end
                        and row in eligible and (activated_at is None or row[2] < activated_at))
            failure = self.conflict(previous, row)
            following = next((r for r in protected if r[2] >= row[2]),None) if can_skip else None
            if failure is None and following is not None:
                failure = self.conflict(row, following)
            if failure is not None:
                if can_skip:
                    # A feasible activation at the SAME departure timestamp
                    # cannot make an incompatible peer a skippable earlier prefix.
                    peers = (peer for peer in ordered if peer != row and peer[2] == row[2])
                    if not any(self.conflict(previous,peer) is None for peer in peers):
                        continue
                raise failure
            result.append(row);previous = row;activated = True
        return result
