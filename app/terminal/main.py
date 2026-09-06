"""Stream-injected deterministic terminal interface for Stage 1 Milestone 7."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_EVEN
import sys

from game.world_state import Stage1BootstrapError

from .formatting import (
    format_basis_points,
    format_money,
    parse_duration_seconds,
    parse_usd_fare,
    parse_utc_timestamp,
)
from .session import Stage1Session


class _EndOfInput(Exception):
    pass


class _Terminal:
    def __init__(self, input_stream, output_stream, session):
        self.input = input_stream
        self.output = output_stream
        self.session = session

    def line(self, text=""):
        self.output.write(f"{text}\n")

    def prompt(self, text, *, allow_blank=False, blank_message=None):
        """Display and flush one question before reading one answer."""
        while True:
            self.line(text)
            self.output.write("> ")
            self.output.flush()
            value = self.input.readline()
            if value == "":
                raise _EndOfInput
            value = value.rstrip("\r\n")
            if value.strip() or allow_blank:
                return value
            self.line(
                blank_message
                or "Blank input is not accepted here; enter a value or 'back'."
            )

    def money(self, value):
        return format_money(
            value, self.session.display_currency, self.session.display_rates
        )

    def confirm_exit(self):
        if not self.session.active:
            return True
        try:
            answer = self.prompt(
                "This temporary session will be lost. Exit? [y/N]",
                allow_blank=True,
            )
        except (_EndOfInput, KeyboardInterrupt):
            self.line()
            return True
        return answer.strip().lower() in {"y", "yes"}

    def startup(self):
        self.line("Airline Tycoon - Stage 1 Temporary Terminal")
        self.line("Sessions are deterministic and in-memory only; exiting loses the session.")
        while True:
            self.line()
            self.line("1. New Stage 1 Game")
            self.line("0. Exit")
            try:
                choice = self.prompt("Select:").strip()
            except KeyboardInterrupt:
                self.line()
                return 0
            if choice == "0":
                return 0
            if choice != "1":
                self.line("Invalid selection. Enter 1 or 0.")
                continue
            try:
                if self.new_game_form():
                    return self.main_menu()
            except KeyboardInterrupt:
                self.line("\nNew-game form cancelled.")

    def new_game_form(self):
        self.line()
        self.line("New Stage 1 Game - stage1-philippines-v1")
        self.line("Blank names are not accepted. Enter 'back' to return.")
        ceo = self.prompt("CEO display name (or back):")
        if ceo.strip().lower() == "back":
            return False
        airline = self.prompt("Airline display name (or back):")
        if airline.strip().lower() == "back":
            return False
        airports = self.session.available_airports()
        self.line("Choose home base:")
        for number, airport in enumerate(airports, 1):
            self.line(
                f"{number}. {airport['reference_code']} - "
                f"{airport['display_name']} - {airport['city']}"
            )
        self.line("0. Back")
        while True:
            choice = self.prompt("Select base by number:").strip()
            if choice == "0" or choice.lower() == "back":
                return False
            if choice.isdigit() and 1 <= int(choice) <= len(airports):
                break
            self.line("Invalid base selection. Enter a listed number or 0 to go back.")
        try:
            self.session.new_game(
                ceo, airline, airports[int(choice) - 1]["reference_code"]
            )
        except Stage1BootstrapError as exc:
            self.line(f"REJECTED [{exc.code}]: {exc}")
            return False
        overview = self.session.overview()
        fleet = self.session.fleet()
        self.line(
            f"Created {overview['airline_display_name']} at "
            f"{overview['base_airports'][0]['reference_code']} on "
            f"{overview['simulation_time_utc']}."
        )
        self.line(
            f"Starter aircraft: {fleet[0]['display_registration']} "
            f"{fleet[0]['model_reference']} (180 Economy seats, free bootstrap grant)."
        )
        return True

    def main_menu(self):
        while True:
            self.line()
            self.line("Main Menu")
            self.line("1. Airline Overview")
            self.line("2. Fleet")
            self.line("3. Plan Weekly Rotation")
            self.line("4. Flights and Bookings")
            self.line("5. Advance Time")
            self.line("6. Financial Results")
            self.line("7. Publish Next Rotation")
            self.line("8. Display Currency")
            self.line("9. Market Research")
            self.line("0. Exit")
            try:
                choice = self.prompt("Select:").strip()
            except (_EndOfInput, KeyboardInterrupt):
                self.line()
                if self.confirm_exit():
                    return 0
                continue
            actions = {
                "1": self.show_overview,
                "2": self.show_fleet,
                "3": self.plan_rotation,
                "4": self.show_flights,
                "5": self.time_menu,
                "6": self.show_finances,
                "7": self.publish_next,
                "8": self.currency_menu,
                "9": self.market_research,
            }
            if choice == "0":
                if self.confirm_exit():
                    return 0
            elif choice in actions:
                try:
                    actions[choice]()
                except KeyboardInterrupt:
                    self.line("\nAction cancelled; no partial form was applied.")
                except _EndOfInput:
                    if self.confirm_exit():
                        return 0
            else:
                self.line("Invalid selection. Enter a listed number.")

    def show_overview(self):
        view = self.session.overview()
        self.line()
        self.line(f"Airline: {view['airline_display_name']} ({view['airline_id']})")
        self.line(f"CEO: {view['ceo_display_name']}")
        self.line(f"Base: {', '.join(item['reference_code'] for item in view['base_airports'])}")
        self.line(f"Authoritative currency: {view['base_currency']}")
        self.line(f"Simulation time: {view['simulation_time_utc']} ({view['clock_state']})")

    def show_fleet(self):
        rows = self.session.fleet()
        self.line()
        self.line("Fleet")
        if not rows:
            self.line("No aircraft.")
            return
        for number, row in enumerate(rows, 1):
            location = row["current_airport_reference_code"] or "IN FLIGHT"
            self.line(
                f"{number}. {row['display_registration']} {row['model_reference']} - "
                f"{row['status']} at {location} [{row['aircraft_id']}]"
            )

    @staticmethod
    def _demand_text(value):
        if not isinstance(value, Decimal):
            return "Unavailable"
        rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
        return f"{rounded:,.2f}".rstrip("0").rstrip(".")

    def market_research(self):
        airports = self.session.airports()
        by_code = {airport["reference_code"]: airport for airport in airports}
        base_code = self.session.overview()["base_airports"][0]["reference_code"]
        self.line()
        self.line("Market Research - active Philippines v1 origins")
        for airport in airports:
            self.line(
                f"{airport['reference_code']} - {airport['display_name']} - "
                f"{airport['city']}"
            )
        while True:
            origin_text = self.prompt(
                f"Origin airport code [{base_code}] (or back):",
                allow_blank=True,
            ).strip().upper()
            if origin_text == "BACK":
                return
            origin_code = origin_text or base_code
            if origin_code in by_code:
                break
            self.line("Invalid origin. Enter a displayed IATA code, blank for base, or back.")

        self.line("Sort destinations:")
        self.line("1. Highest base daily demand")
        self.line("2. Airport code")
        self.line("3. Distance")
        while True:
            sort_choice = self.prompt(
                "Sort [1]:", allow_blank=True
            ).strip() or "1"
            if sort_choice in {"1", "2", "3"}:
                break
            self.line("Invalid sort. Enter 1, 2, or 3.")
        rows = self.session.market_opportunities(
            origin_airport_id=origin_code, limit=100
        )
        if sort_choice == "1":
            rows.sort(key=lambda row: (
                -row["base_daily_directional_bookers"],
                row["destination_airport_reference_code"],
                row["market_id"],
            ))
        elif sort_choice == "2":
            rows.sort(key=lambda row: (
                row["destination_airport_reference_code"], row["market_id"]
            ))
        else:
            rows.sort(key=lambda row: (
                row["distance_km"],
                row["destination_airport_reference_code"],
                row["market_id"],
            ))
        origin = by_code[origin_code]
        while True:
            self.line()
            self.line(
                f"MARKET RESEARCH - FROM {origin['city'].upper()} ({origin_code})"
            )
            for number, row in enumerate(rows, 1):
                self.line(
                    f"{number}. {row['destination_airport_reference_code']} - "
                    f"{row['destination_airport_city']}"
                )
                self.line(
                    "   Base daily market demand: "
                    + self._demand_text(row["base_daily_directional_bookers"])
                )
                self.line(f"   Distance: {row['distance_km']:,.0f} km")
                self.line(
                    f"   Your scheduled seats: {row['player_published_capacity']}"
                )
                self.line(
                    "   Your service: "
                    + ("Scheduled" if row["qualifying_player_service_exists"] else "None")
                )
            self.line()
            self.line(
                "Base daily market demand represents total directional market demand. "
                "It does not guarantee that every passenger will choose your airline."
            )
            self.line("0. Back")
            choice = self.prompt("View market details by number:").strip()
            if choice == "0" or choice.lower() == "back":
                return
            if not choice.isdigit() or not 1 <= int(choice) <= len(rows):
                self.line("Invalid market selection. Enter a listed number or 0.")
                continue
            row = rows[int(choice) - 1]
            self.line()
            self.line(
                f"{origin_code} - {row['destination_airport_reference_code']}: "
                f"{origin['city']} to {row['destination_airport_city']}"
            )
            self.line(f"Destination airport: {row['destination_airport_name']}")
            self.line(
                "Base daily directional market demand: "
                + self._demand_text(row["base_daily_directional_bookers"])
            )
            self.line(f"Distance: {row['distance_km']:,.0f} km")
            self.line(
                "Market availability: "
                + ("Available" if row["market_available"] else "Unavailable")
            )
            self.line(
                "Your qualifying service: "
                + ("Scheduled" if row["qualifying_player_service_exists"] else "None")
            )
            self.line(f"Your published seats: {row['player_published_capacity']}")
            fare = row["player_fare_minor"]
            self.line(
                "Your fare: "
                + (
                    self.money(fare)
                    if fare is not None
                    else "None or not unambiguous"
                )
            )
            self.line(
                f"Current confirmed bookings: {row['current_confirmed_bookings']}"
            )
            self.line(
                "Actual bookings depend on fare, schedule, capacity, and future competition."
            )
            self.prompt("Press Enter to return to the destination list.", allow_blank=True)

    def plan_rotation(self):
        fleet = self.session.fleet()
        self.line()
        self.line("Select parked aircraft:")
        for number, aircraft in enumerate(fleet, 1):
            self.line(
                f"{number}. {aircraft['display_registration']} at "
                f"{aircraft['current_airport_reference_code']}"
            )
        self.line("0. Back")
        while True:
            choice = self.prompt("Aircraft:").strip()
            if choice == "0" or choice.lower() == "back":
                return
            if choice.isdigit() and 1 <= int(choice) <= len(fleet):
                break
            self.line("Invalid aircraft selection. Enter a listed number.")
        aircraft = fleet[int(choice) - 1]
        if aircraft["status"] != "PARKED":
            self.line("REJECTED [AIRCRAFT_NOT_PARKED]: select a parked aircraft.")
            return
        origin = aircraft["current_airport_reference_code"]
        destinations = tuple(
            airport for airport in self.session.airports()
            if airport["reference_code"] != origin
        )
        self.line(f"Origin: {origin}")
        for number, airport in enumerate(destinations, 1):
            self.line(
                f"{number}. {airport['reference_code']} - "
                f"{airport['display_name']} - {airport['city']}"
            )
        self.line("0. Back")
        while True:
            choice = self.prompt("Destination:").strip()
            if choice == "0" or choice.lower() == "back":
                return
            if choice.isdigit() and 1 <= int(choice) <= len(destinations):
                break
            self.line("Invalid destination selection. Enter a listed number.")
        destination = destinations[int(choice) - 1]["reference_code"]
        while True:
            fare_text = self.prompt(
                "Economy fare in USD (e.g. 99.50, or back):"
            ).strip()
            if fare_text.lower() == "back":
                return
            try:
                fare_minor = parse_usd_fare(fare_text)
                break
            except ValueError as exc:
                self.line(f"Invalid fare: {exc}")
        default_date = self.session.default_operating_date()
        while True:
            date_text = self.prompt(
                f"First operating date YYYY-MM-DD [{default_date}] (or back):",
                allow_blank=True,
            ).strip()
            if date_text.lower() == "back":
                return
            date_text = date_text or default_date
            try:
                parsed = date.fromisoformat(date_text)
                if parsed.isoformat() != date_text:
                    raise ValueError
                break
            except ValueError:
                self.line("Invalid date: expected canonical YYYY-MM-DD.")
        current = date.fromisoformat(self.session.overview()["simulation_time_utc"][:10])
        if (parsed - current).days < 6:
            self.line("Warning: this departure is too near to receive useful daily Bookings.")
            if self.prompt("Continue anyway? [y/N]", allow_blank=True).strip().lower() not in {"y", "yes"}:
                return
        self.line(
            f"Review: {origin}-{destination} 08:00-10:00, "
            f"{destination}-{origin} 12:00-14:00 weekly from {date_text}; "
            f"fare {self.money(fare_minor)} both ways."
        )
        if self.prompt("Publish first outbound and return? [y/N]", allow_blank=True).strip().lower() not in {"y", "yes"}:
            self.line("Rotation cancelled.")
            return
        result = self.session.plan_rotation(
            aircraft["aircraft_id"], destination, fare_minor, date_text
        )
        if not result.succeeded:
            issue = result.issues[0]
            self.line(f"{result.status} [{issue.code}]: {issue.message}")
            return
        self.line(
            f"Published rotation with {len(result.dated_flight_ids)} flights: "
            + ", ".join(result.dated_flight_ids)
        )

    def show_flights(self):
        rows = self.session.flights()
        self.line()
        self.line("Flights and Bookings (maximum 20)")
        if not rows:
            self.line("No published flights.")
            return
        for number, row in enumerate(rows, 1):
            self.line(
                f"{number}. {row['origin_airport_reference_code']}-"
                f"{row['destination_airport_reference_code']} "
                f"{row['scheduled_departure_utc']} {row['status']} "
                f"{row['aircraft_registration']}"
            )
            self.line(
                f"   Fare {self.money(row['fare_minor'])}; booked "
                f"{row['booked_passenger_count']}/{row['published_capacity']} "
                f"({format_basis_points(row['booked_load_factor_basis_points'])}), "
                f"remaining {row['remaining_capacity']}; ticket sales "
                f"{self.money(row['ticket_sales_minor'])}"
            )
            if row["status"] in {"OPERATIONALLY_LOCKED", "COMPLETED"}:
                self.line(
                    f"   Carried {row['carried_passenger_count']} "
                    f"({format_basis_points(row['carried_load_factor_basis_points'])}); "
                    f"revenue {self.money(row['recognized_revenue_minor'])}; "
                    f"cost {self.money(row['operating_cost_minor'])}; "
                    f"profit/loss {self.money(row['operating_profit_minor'])}"
                )
            event = row["next_lifecycle_event"]
            if event:
                self.line(f"   Next: {event['event_type']} at {event['due_at_utc']}")

    def time_menu(self):
        while True:
            self.line()
            self.line("Advance Time")
            self.line("1. Advance to Next Event")
            self.line("2. Advance One Day")
            self.line("3. Advance by Duration")
            self.line("4. Advance to UTC Timestamp")
            self.line("0. Back")
            choice = self.prompt("Select: ").strip()
            if choice == "0":
                return
            try:
                if choice == "1":
                    event = self.session.next_event()
                    if event:
                        self.line(f"Next event: {event['event_type']} at {event['due_at_utc']}")
                    report = self.session.advance_next_event()
                elif choice == "2":
                    report = self.session.advance_seconds(86400)
                elif choice == "3":
                    text = self.prompt("Duration (30m, 6h, 1d; or back): ").strip()
                    if text.lower() == "back":
                        continue
                    report = self.session.advance_seconds(parse_duration_seconds(text))
                elif choice == "4":
                    text = self.prompt("UTC timestamp YYYY-MM-DDTHH:MM:SSZ (or back): ").strip()
                    if text.lower() == "back":
                        continue
                    report = self.session.advance_to(parse_utc_timestamp(text))
                else:
                    self.line("Invalid selection. Enter a listed number.")
                    continue
            except ValueError as exc:
                self.line(f"Invalid time request: {exc}")
                continue
            except KeyboardInterrupt:
                self.line("\nTime advancement interrupted at a committed boundary.")
                self.line(
                    f"Simulation time: {self.session.overview()['simulation_time_utc']}"
                )
                event = self.session.next_event()
                if event:
                    self.line(
                        f"Pending next event: {event['event_id']} "
                        f"{event['event_type']} at {event['due_at_utc']}"
                    )
                if not self.session.validate():
                    raise RuntimeError("interrupted session failed validation")
                continue
            self.show_advancement(report)

    def show_advancement(self, report):
        result = report.result
        self.line(f"Simulation time: {result.ended_at_utc}")
        for row in report.event_rows:
            self.line(f"{row['status']}: {row['event_id']} {row['event_type']}")
        if result.skipped_event_ids:
            self.line("Skipped stale events: " + ", ".join(result.skipped_event_ids))
        if result.failure:
            self.line(
                f"BLOCKED [{result.failure.code}] event "
                f"{result.failure.event_id or '-'}: {result.failure.message}"
            )

    def show_finances(self):
        view = self.session.finances()
        self.line()
        self.line("Financial Results - authoritative USD accounting")
        self.line(f"Cash: {self.money(view['cash_minor'])}")
        self.line(f"Unflown-ticket liability: {self.money(view['unflown_ticket_liability_minor'])}")
        self.line(f"Passenger revenue: {self.money(view['passenger_revenue_minor'])}")
        self.line(f"Operating expenses: {self.money(view['operating_expenses_minor'])}")
        self.line(f"Cumulative fulfilment revenue: {self.money(view['cumulative_revenue_minor'])}")
        self.line(f"Cumulative fulfilment cost: {self.money(view['cumulative_cost_minor'])}")
        self.line(f"Cumulative operating contribution: {self.money(view['cumulative_profit_minor'])}")
        self.line(f"Recent results: {len(view['recent_results'])}; recent transactions: {len(view['recent_transactions'])}")

    def publish_next(self):
        result = self.session.publish_next_rotation()
        if not result.succeeded:
            issue = result.issues[0]
            self.line(f"{result.status} [{issue.code}]: {issue.message}")
            return
        self.line(
            f"Published {len(result.dated_flight_ids)} next weekly occurrence(s) "
            f"for {result.first_operating_date}."
        )

    def currency_menu(self):
        before = self.session.authoritative_bytes()
        currencies = ("USD", "PHP", "EUR")
        self.line("Display Currency (authoritative accounting always remains USD)")
        for number, code in enumerate(currencies, 1):
            self.line(f"{number}. {code}")
        self.line("0. Back")
        choice = self.prompt("Select: ").strip()
        if choice == "0":
            return
        if not choice.isdigit() or not 1 <= int(choice) <= len(currencies):
            self.line("Invalid display-currency selection.")
            return
        self.session.set_display_currency(currencies[int(choice) - 1])
        if self.session.authoritative_bytes() != before:
            raise RuntimeError("display currency mutated authoritative world")
        self.line(
            f"Display currency set to {self.session.display_currency}; USD remains authoritative."
        )


def run_terminal(input_stream, output_stream, *, session_factory=Stage1Session):
    """Run the harness using injected text streams and deterministic newlines."""
    terminal = None
    try:
        terminal = _Terminal(input_stream, output_stream, session_factory())
        return terminal.startup()
    except _EndOfInput:
        if terminal is None or terminal.confirm_exit():
            return 0
        return 0
    except Exception as exc:
        integrity = terminal is None or terminal.session.validate()
        output_stream.write(
            f"Terminal ended safely after an unexpected error: {type(exc).__name__}: {exc}\n"
        )
        if not integrity:
            output_stream.write("Authoritative world validation failed; the session cannot continue.\n")
        return 1


def main():
    return run_terminal(sys.stdin, sys.stdout)


__all__ = ("main", "run_terminal")
