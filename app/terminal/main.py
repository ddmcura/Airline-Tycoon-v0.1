"""Stream-injected deterministic terminal interface for Stage 1 Milestone 7."""

from __future__ import annotations

from datetime import date, timedelta
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_EVEN
import sys
import time
from collections import deque

from game.world_state import Stage1BootstrapError
from game.world_state.persistence import SaveError

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
    def __init__(self, input_stream, output_stream, session, *, input_source=None):
        self.input = input_stream
        self.output = output_stream
        self.session = session
        self.input_source = input_source
        self.pending_input = deque()
        self.interrupt_requested = False
        self.last_status = 0
        self.last_diagnostic = None
        self.last_autosave_error = None
        self.session.on_advance_boundary = self.advance_boundary

    def clock_status(self):
        if self.session.active:
            clock = self.session.world['simulation']
            self.line(f"Clock: {clock['time_utc']} | {clock['clock_state']} | 7x | /pause /resume /status")
            runtime = self.session.runtime
            if runtime and runtime.diagnostic != self.last_diagnostic:
                if runtime.diagnostic:
                    self.line(runtime.diagnostic)
                self.last_diagnostic = runtime.diagnostic
            if self.session.autosave_error != self.last_autosave_error:
                if self.session.autosave_error:
                    self.line(f"Autosave failed: {self.session.autosave_error}")
                self.last_autosave_error = self.session.autosave_error

    def read_answer(self):
        if self.pending_input:
            return self.pending_input.popleft()
        if self.input_source is None:
            return self.input.readline()
        while True:
            if self.interrupt_requested:
                self.interrupt_requested = False
                if self.session.active:
                    self.session.pause()
                raise KeyboardInterrupt
            value = self.input_source.poll(0)
            if value is not None:
                if value and value.strip().lower() != '/pause':
                    self.session.pump()
                return value
            self.session.pump()
            if time.monotonic() - self.last_status >= 1:
                self.clock_status()
                self.output.flush()
                self.last_status = time.monotonic()
            # Do not busy-poll while waiting for the next pacing second.
            value = self.input_source.poll(.02)
            if value is not None:
                return value

    def advance_boundary(self):
        """Only control input is applied inside a bulk processing command."""
        value = self.input_source.poll(0) if self.input_source else None
        if value == '' or (value and value.strip().lower() == '/pause') or self.interrupt_requested:
            self.interrupt_requested = False
            self.session.pause()
            if value == '':
                self.pending_input.append(value)
        elif value is not None:
            self.line('Bulk advancement is active; use /pause to stop before another action.')
        if self.input_source and time.monotonic() - self.last_status >= 1:
            self.clock_status()
            self.output.flush()
            self.last_status = time.monotonic()

    def line(self, text=""):
        self.output.write(f"{text}\n")

    def prompt(self, text, *, allow_blank=False, blank_message=None):
        """Display and flush one question before reading one answer."""
        while True:
            self.clock_status()
            self.line(text)
            self.output.write("> ")
            self.output.flush()
            value = self.read_answer()
            if value == "":
                raise _EndOfInput
            value = value.rstrip("\r\n")
            if self.session.active and value.strip().lower() in {'/pause', '/resume', '/status'}:
                command = value.strip().lower()
                if command == '/pause':
                    self.session.pause()
                elif command == '/resume':
                    self.session.resume()
                continue
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
        if not self.session.unsaved_progress:
            return True
        try:
            answer = self.prompt(
                "Unsaved progression. [s] Save and leave / [d] Leave without saving / [c] Cancel",
                allow_blank=True,
            )
        except (_EndOfInput, KeyboardInterrupt):
            self.line()
            return True
        answer = answer.strip().lower()
        if answer in {'s', 'save'}:
            try:
                self.session.save_manual()
            except SaveError as exc:
                self.line(f"Save failed [{exc.code}]: {exc}")
                return False
            self.line('Game saved.')
            return True
        return answer in {'d', 'discard', 'y', 'yes'}

    def startup(self):
        self.line("Airline Tycoon - Stage 1 Terminal")
        while True:
            self.line()
            self.line("1. New Stage 1 Game")
            self.line("2. Load Game")
            self.line("0. Exit")
            try:
                choice = self.prompt("Select:").strip()
            except KeyboardInterrupt:
                self.line()
                return 0
            if choice == "0":
                return 0
            if choice not in {"1", "2"}:
                self.line("Invalid selection. Enter 1, 2 or 0.")
                continue
            try:
                ready = self.new_game_form() if choice == '1' else self.load_game_menu()
                if ready:
                    result = self.main_menu()
                    if result != 'TITLE':
                        return result
            except KeyboardInterrupt:
                self.line("\nAction cancelled.")

    def load_game_menu(self):
        careers = self.session.list_careers()
        if not careers:
            self.line('No saved airline games found.')
            return False
        self.line('Load Game')
        for index, career in enumerate(careers, 1):
            self.line(f"{index}. {career['airline_name']} - {career['simulation_time_utc']}")
        self.line('0. Back')
        choice = self.prompt('Select airline:').strip()
        if choice == '0' or choice.lower() == 'back':
            return False
        if not choice.isdigit() or not 1 <= int(choice) <= len(careers):
            self.line('Invalid airline selection.')
            return False
        career = careers[int(choice) - 1]
        if career.get('unreadable'):
            if career.get('diagnostic') == 'NEWER_SCHEMA':
                self.line('Load failed [NEWER_SCHEMA]: This game uses a newer unsupported save schema.')
            else:
                self.line('Load failed [CORRUPT_FILE]: This career has no readable save or recovery copy.')
            return False
        career_id = career['career_id']
        bookmarks = self.session.list_bookmarks(career_id)
        if bookmarks:
            if not career['has_manual'] and not career['has_autosave']:
                action = 'b'
            else:
                action = self.prompt('Load current game, or [b] browse bookmarks?',
                                     allow_blank=True).strip().lower()
            if action == 'b':
                for index, row in enumerate(bookmarks, 1):
                    self.line(f"{index}. {row['name']} - {row['simulation_time_utc']}")
                bookmark_choice = self.prompt('Select bookmark (0 to cancel):').strip()
                if not bookmark_choice.isdigit() or not 1 <= int(bookmark_choice) <= len(bookmarks):
                    return False
                row = bookmarks[int(bookmark_choice) - 1]
                return self._load_choice(career_id, 'bookmark', bookmark_id=row['bookmark_id'])
        kind = 'manual'
        if not career['has_manual']:
            kind = 'autosave'
        elif self.session.newer_autosave(career_id):
            recovery = self.prompt('Newer autosave found. [a] Autosave / [m] Manual / [c] Cancel:').strip().lower()
            if recovery in {'a', 'autosave'}:
                kind = 'autosave'
            elif recovery not in {'m', 'manual'}:
                return False
        return self._load_choice(career_id, kind)

    def _load_choice(self, career_id, kind, *, bookmark_id=None):
        try:
            data = self.session.load_saved(career_id, kind, bookmark_id=bookmark_id)
        except SaveError as exc:
            self.line(f"Load failed [{exc.code}]: {exc}")
            return False
        self.line(f"Loaded {self.session.overview()['airline_display_name']} at "
                  f"{self.session.world['simulation']['time_utc']} (paused; {data['kind']}).")
        if data.get('_recovered_from_previous'):
            self.line('Loaded the previous valid recovery copy; the current file was unusable.')
        return True

    def save_game(self):
        try:
            self.session.save_manual()
            self.line('Game saved.')
        except SaveError as exc:
            self.line(f"Save failed [{exc.code}]: {exc}")

    def bookmarks_menu(self):
        while True:
            bookmarks = self.session.list_bookmarks()
            self.line('Bookmarks')
            for index, row in enumerate(bookmarks, 1):
                self.line(f"{index}. {row['name']} - {row['simulation_time_utc']}")
            self.line('[n] New / [l] Load / [d] Delete / 0 Back')
            action = self.prompt('Select:').strip().lower()
            if action in {'0', 'back'}:
                return
            if action == 'n':
                name = self.prompt('Bookmark name:').strip()
                try:
                    self.session.save_bookmark(name)
                    self.line('Bookmark saved.')
                except SaveError as exc:
                    self.line(f"Bookmark failed [{exc.code}]: {exc}")
                continue
            if action in {'l', 'd'}:
                number = self.prompt('Bookmark number (0 to cancel):').strip()
                if not number.isdigit() or not 1 <= int(number) <= len(bookmarks):
                    continue
                row = bookmarks[int(number) - 1]
                if action == 'l':
                    if not self.confirm_exit():
                        continue
                    self._load_choice(self.session.career_id, 'bookmark', bookmark_id=row['bookmark_id'])
                    return
                confirmation = self.prompt(f"Delete bookmark {row['name']}? [y/N]", allow_blank=True)
                if confirmation.strip().lower() in {'y', 'yes'}:
                    try:
                        self.session.save_store.delete_bookmark(self.session.career_id, row['bookmark_id'])
                        self.line('Bookmark deleted.')
                    except SaveError as exc:
                        self.line(f"Delete failed [{exc.code}]: {exc}")

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
            self.line("3. Weekly Scheduler")
            self.line("4. Flights and Bookings")
            self.line("5. Advance Time")
            self.line("6. Financial Results")
            self.line("7. Publish Next Rotation")
            self.line("8. Display Currency")
            self.line("9. Market Research")
            self.line("10. Quick fixed weekly round trip")
            self.line("11. Aircraft Catalogue")
            self.line("12. Purchase New Aircraft")
            self.line("13. Leasing Marketplace")
            self.line("14. Used Aircraft Marketplace")
            self.line("15. Save Game")
            self.line("16. Bookmarks")
            self.line("17. Return to Title")
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
                "3": self.weekly_scheduler,
                "4": self.show_flights,
                "5": self.time_menu,
                "6": self.show_finances,
                "7": self.publish_next,
                "8": self.currency_menu,
                "9": self.market_research,
                "10": self.plan_rotation,
                "11": self.aircraft_catalogue,
                "12": lambda: self.aircraft_catalogue(purchase=True),
                "13": self.leasing_marketplace,
                "14": self.used_aircraft_marketplace,
                "15": self.save_game,
                "16": self.bookmarks_menu,
            }
            if choice == "0":
                if self.confirm_exit():
                    return 0
            elif choice == '17':
                if self.confirm_exit():
                    self.session.leave_game()
                    return 'TITLE'
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

    def _choose_delivery(self):
        rows = self.session.delivery_locations()
        choices = {str(index): row for index, row in enumerate(rows, 1)}
        for key, row in choices.items():
            self.line(f"{key}. {row['reference_code']} - {row['display_name']}")
        choice = self.prompt("Delivery location (number or back):").strip().lower()
        return None if choice in {"0", "back", "cancel"} else choices.get(choice)

    def leasing_marketplace(self):
        while True:
            offers = self.session.leasing_offers()
            self.line("Leasing Marketplace - current offers")
            for index, row in enumerate(offers, 1):
                self.line(f"{index}. {row['model_id']} - {row['available_quantity']} available; "
                          f"value {self.money(row['aircraft_value_minor'])}")
            self.line("R. Renew an operating lease | T. End a contract | 0. Back")
            choice = self.prompt("Select offer or action:").strip().lower()
            if choice in {"0", "back", "cancel"}:
                return
            try:
                if choice == "r":
                    contracts = [row for row in self.session.aircraft_contracts()
                                 if row['contract_type'] == 'OPERATING_LEASE' and row['status'] == 'ACTIVE']
                    for index, row in enumerate(contracts, 1):
                        self.line(f"{index}. {row['aircraft_id']} expires {row['expires_at_utc']}")
                    selected = self.prompt("Contract number or back:").strip()
                    if selected not in {str(i) for i in range(1, len(contracts) + 1)}:
                        continue
                    row = contracts[int(selected) - 1]
                    term = int(self.prompt("Renewal term in years (1-5):").strip())
                    quote = self.session.preview_operating_renewal(row['aircraft_id'], term)
                    self.line(f"New monthly rent: {self.money(quote.monthly_rent_minor)} "
                              f"through {quote.expires_at_utc}.")
                    if self.prompt("Confirm renewal? [y/N]", allow_blank=True).strip().lower() not in {'y', 'yes'}:
                        continue
                    command = f"terminal-renew-{row['aircraft_id']}-{row['expires_at_utc']}-{term}"
                    contract_id = self.session.renew_operating_lease(
                        row['aircraft_id'], term, command, quote.world_fingerprint)
                    self.line(f"Renewal confirmed as {contract_id}.")
                    continue
                if choice == "t":
                    contracts = [row for row in self.session.aircraft_contracts() if row['status'] == 'ACTIVE']
                    for index, row in enumerate(contracts, 1):
                        self.line(f"{index}. {row['aircraft_id']} {row['contract_type']} expires {row['expires_at_utc']}")
                    selected = self.prompt("Contract number or back:").strip()
                    if selected not in {str(i) for i in range(1, len(contracts) + 1)}:
                        continue
                    row = contracts[int(selected) - 1]
                    if self.prompt("Return aircraft and settle now? [y/N]", allow_blank=True).strip().lower() not in {'y', 'yes'}:
                        continue
                    command = f"terminal-end-{row['aircraft_id']}-{self.session.world['simulation']['time_utc']}"
                    settlement = self.session.terminate_contract(row['aircraft_id'], command)
                    self.line(f"Contract ended; net cash settlement {self.money(settlement)}.")
                    continue
                if choice not in {str(i) for i in range(1, len(offers) + 1)}:
                    self.line("Invalid leasing selection.")
                    continue
                offer = offers[int(choice) - 1]
                product = self.prompt("1 Operating lease | 2 Lease-to-own:").strip()
                contract_type = {'1': 'OPERATING_LEASE', '2': 'LEASE_TO_OWN'}.get(product)
                term = int(self.prompt("Term in years (1-5):").strip())
                location = self._choose_delivery()
                if contract_type is None or location is None:
                    continue
                preview = self.session.preview_lease(offer['lease_offer_id'], contract_type,
                                                     term, location['airport_id'])
                monthly = preview.monthly_rent_minor or (
                    preview.monthly_financing_minor + preview.principal_base_minor
                    + (1 if preview.principal_remainder_installments else 0))
                self.line(f"Monthly payment starts at {self.money(monthly)}; cash may become negative.")
                if self.prompt("Confirm contract? [y/N]", allow_blank=True).strip().lower() in {'y', 'yes'}:
                    aircraft_id = self.session.accept_lease(preview)
                    self.line(f"Aircraft delivered as {aircraft_id}.")
            except (ValueError, KeyError) as exc:
                self.line(f"Lease rejected: {exc}")

    def used_aircraft_marketplace(self):
        listings = self.session.used_listings()
        self.line("Used Aircraft Marketplace - unsold listings persist monthly")
        for index, row in enumerate(listings, 1):
            self.line(f"{index}. {row['display_registration']} {row['model_id']} - "
                      f"{row['age_months']} months, {row['lifetime_cycles']:,} cycles, "
                      f"condition {row['service_condition_bps'] / 100:.2f}% - "
                      f"{self.money(row['asking_price_minor'])}")
        choice = self.prompt("Listing number or back:").strip().lower()
        if choice not in {str(i) for i in range(1, len(listings) + 1)}:
            return
        location = self._choose_delivery()
        if location is None:
            return
        try:
            preview = self.session.preview_used_purchase(
                listings[int(choice) - 1]['used_listing_id'], location['airport_id'])
            self.line(f"Cash after purchase: {self.money(preview.cash_after_minor)}")
            if preview.cash_after_minor < 0:
                self.line("Insufficient cash. No purchase made.")
                return
            if self.prompt("Confirm purchase? [y/N]", allow_blank=True).strip().lower() in {'y', 'yes'}:
                aircraft_id = self.session.purchase_used(preview)
                self.line(f"Specific airframe delivered as {aircraft_id}.")
        except (ValueError, KeyError) as exc:
            self.line(f"Used-aircraft purchase rejected: {exc}")

    def aircraft_catalogue(self, *, purchase=False):
        try:
            catalog = self.session.aircraft_catalog()
        except (OSError, ValueError) as exc:
            self.line(f"Aircraft catalogue unavailable: {exc}")
            return
        self.line("Aircraft Catalogue - reference models and game prices")
        self.line("Choose a model to preview its purchase." if purchase else
                  "Select Purchase New Aircraft, Leasing Marketplace, or Used Aircraft Marketplace from the main menu.")
        manufacturers = catalog.manufacturers()
        while True:
            for number, row in enumerate(manufacturers, 1):
                self.line(f"{number}. {row['display_name']}")
            choice = self.prompt("Manufacturer (number, back, or cancel):").strip().lower()
            if choice in {"0", "back", "cancel"}:
                return
            # Compare strings instead of converting arbitrary user input to int.
            choices = {str(i): row for i, row in enumerate(manufacturers, 1)}
            if choice not in choices:
                self.line("Invalid manufacturer selection.")
                continue
            manufacturer = choices[choice]
            self.line(manufacturer["notes"])
            models = catalog.models(manufacturer["manufacturer_id"])
            while True:
                for number, row in enumerate(models, 1):
                    self.line(f"{number}. {row['display_name']} - {row['max_economy_seats']} Economy seats")
                choice = self.prompt("Model (number, back, or cancel):").strip().lower()
                if choice == "cancel":
                    return
                if choice in {"0", "back"}:
                    break
                choices = {str(i): row for i, row in enumerate(models, 1)}
                if choice not in choices:
                    self.line("Invalid model selection.")
                    continue
                view = catalog.model(choices[choice]["model_id"])
                model, price = view["model"], view["reference_price"]
                self.line(f"\n{model['display_name']} - {manufacturer['display_name']}")
                self.line(f"Maximum Economy layout: {model['max_economy_seats']} seats")
                self.line(f"Reference range: {model['reference_range_km']:,} km (configuration-dependent)")
                self.line(f"Calibrated cruise speed: {model['cruise_speed_kph']} km/h")
                self.line(f"Game reference price: {self.money(price['amount_minor'])}")
                start, end = model["production_start_year"], model["production_end_year"]
                self.line(f"Production start: {start if start is not None else 'Unestablished'}; "
                          f"production end: {end if end is not None else 'Unestablished'}")
                self.line("Production dates do not restrict this catalogue.")
                self.line(model["notes"])
                self.line(f"Reference version: {view['catalog_version']}")
                if purchase:
                    self.purchase_model(model)
                    return

    def purchase_model(self, model):
        locations = self.session.delivery_locations()
        choices = {str(i): row for i, row in enumerate(locations, 1)}
        for key, row in choices.items():
            self.line(f"{key}. {row['reference_code']} - {row['display_name']}")
        while True:
            choice = self.prompt('Delivery location (number, back, or cancel):').strip().lower()
            if choice in {'0', 'back', 'cancel'}:
                return
            if choice in choices:
                break
            self.line('Invalid delivery location.')
        try:
            location = choices[choice]
            preview = self.session.preview_purchase(model['model_id'], location['airport_id'])
            self.line(f"Purchase one {model['display_name']}, {model['max_economy_seats']} Economy seats.")
            self.line(f"Immediate delivery: {location['reference_code']}; parked and ready for Weekly Scheduler.")
            self.line(f"Price: {self.money(preview.amount_minor)}; cash after: {self.money(preview.cash_after_minor)}")
            if preview.cash_after_minor < 0:
                self.line('Insufficient cash. No purchase made.')
                return
            while True:
                confirm = self.prompt('Confirm purchase (yes/no):').strip().lower()
                if confirm in {'no', 'n', '0', 'back', 'cancel'}:
                    return
                if confirm in {'yes', 'y'}:
                    break
                self.line('Enter yes or no.')
            aircraft_id = self.session.purchase(preview)
            aircraft = self.session.world['world_state']['aircraft'][aircraft_id]
            self.line(f"Purchased {aircraft['display_registration']} at {location['reference_code']}.")
        except (ValueError, OSError) as exc:
            self.line(f'Purchase rejected: {exc}')

    def select_aircraft(self):
        offset = 0
        while True:
            fleet = self.session.fleet(offset=offset)
            choices = {str(i): row for i, row in enumerate(fleet, 1)}
            for key, row in choices.items():
                self.line(f"{key}. {row['display_registration']} {row['model_reference']} "
                          f"({row['status']}) at {row['current_airport_reference_code'] or 'IN FLIGHT'}")
            choice = self.prompt('Choose plane (number, next, previous, 0 back):').strip().lower()
            if choice in {'0', 'back', 'cancel'}:
                return None
            if choice == 'next':
                if self.session.fleet(offset=offset + 20, limit=1):
                    offset += 20
                else:
                    self.line('Last page.')
            elif choice == 'previous':
                offset = max(0, offset - 20)
            elif choice in choices:
                return choices[choice]
            else:
                self.line('Invalid aircraft selection.')

    def show_overview(self):
        view = self.session.overview()
        self.line()
        self.line(f"Airline: {view['airline_display_name']} ({view['airline_id']})")
        self.line(f"CEO: {view['ceo_display_name']}")
        self.line(f"Base: {', '.join(item['reference_code'] for item in view['base_airports'])}")
        self.line(f"Authoritative currency: {view['base_currency']}")
        self.line(f"Simulation time: {view['simulation_time_utc']} ({view['clock_state']})")

    def show_fleet(self):
        offset = 0
        while True:
            rows = self.session.fleet(offset=offset)
            self.line()
            self.line(f'Fleet - page {offset // 20 + 1}')
            if not rows:
                self.line('No aircraft.')
                return
            for number, row in enumerate(rows, 1):
                location = row['current_airport_reference_code'] or 'IN FLIGHT'
                self.line(f"{number}. {row['display_registration']} {row['model_reference']} - "
                          f"{row['status']} at {location} [{row['aircraft_id']}]")
            following = bool(self.session.fleet(offset=offset + 20, limit=1))
            if not following and offset == 0:
                return
            choice = self.prompt('Fleet page (next, previous, or back):').strip().lower()
            if choice == 'next' and following:
                offset += 20
            elif choice == 'previous':
                offset = max(0, offset - 20)
            elif choice in {'0', 'back', 'cancel'}:
                return
            else:
                self.line('Choose an available page or back.')

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

    def weekly_scheduler(self):
        from game.scheduling.weekly import monday, local_departure
        from game.world_state.timestamps import parse_canonical_utc, format_utc
        from game.world_state.timezones import load_named_timezone
        aircraft = self.select_aircraft()
        if aircraft is None:
            return
        try:
            draft = self.session.begin_scheduling(aircraft['aircraft_id'])
        except ValueError as exc:
            self.line(str(exc))
            return
        airports = self.session.airports()
        codes = {a['reference_code']: a['airport_id'] for a in airports}
        labels = {v: k for k, v in codes.items()}
        zone = load_named_timezone('Asia/Manila')
        week = monday(parse_canonical_utc(self.session.world['simulation']['time_utc']).astimezone(zone).date())
        self.line('Draft only until Save schedule. Times are Philippine local time.')
        self.line('Departure means leaving the stand; blocks include preparation and unloading.')

        def ask(text):
            answer = self.prompt(text + ' (back cancels):').strip()
            if answer.lower() == 'back':
                raise ValueError('Form cancelled.')
            return answer

        def airport(text):
            answer = ask(text).upper()
            if answer not in codes:
                raise ValueError('Choose a listed airport code.')
            return codes[answer]

        while True:
            self.line(f'Week of Monday {week.isoformat()}')
            rows = draft.week_rows(week.isoformat())
            for day in range(7):
                shown = week + timedelta(days=day)
                self.line(f'{day+1}. {shown:%A %Y-%m-%d}')
                for row in rows:
                    if row['reserved_from'][:10] <= shown.isoformat() <= row['reserved_until'][:10]:
                        self.line(f"  {labels[row['origin_airport_id']]} → {labels[row['destination_airport_id']]} "
                                  f"departure {row['departure_local'][11:19]}; reserved "
                                  f"{row['reserved_from'][:19]} to {row['reserved_until'][:19]}")
            self.line('1 Add flight | 2 Next week | 3 Previous week | 4 Copy draft day | 5 Undo last | 6 Save schedule | 0 Cancel draft')
            action = self.prompt('Schedule action:').strip()
            try:
                if action == '0':
                    self.line('Draft cancelled.')
                    return
                if action in {'2', '3'}:
                    week += timedelta(days=7 if action == '2' else -7)
                elif action == '5':
                    draft.undo()
                elif action == '4':
                    source = ask('Source date YYYY-MM-DD')
                    target = ask('Target date YYYY-MM-DD')
                    draft.copy_day(source, target)
                elif action == '6':
                    repeat = self.prompt('Repeat weekly? [y/N]', allow_blank=True).strip().lower()
                    end = ask('Repeat through date YYYY-MM-DD') if repeat in {'y', 'yes'} else None
                    self.line(f'Review: {len(draft.legs)} draft leg(s)' + (f', weekly through {end}.' if end else ', chosen dates only.'))
                    if self.prompt('Save schedule and publish? [y/N]', allow_blank=True).strip().lower() in {'y', 'yes'}:
                        result = self.session.save_scheduling(draft, repeat_until=end)
                        self.line(f'Published {len(result.created_dated_flight_ids)} flights. Schedule saved in this session.')
                        return
                elif action == '1':
                    working = deepcopy(draft)
                    self.line('Airports: ' + ', '.join(codes))
                    continuing = False
                    if draft.legs:
                        continuing = self.prompt('Continue from last stop? [Y/n]', allow_blank=True).strip().lower() not in {'n', 'no'}
                    origin = working.last_stop if continuing else airport('Origin code')
                    destination = airport('Destination code')
                    floor = format_utc(local_departure(self.session.world['world_state'], origin, week.isoformat(), '00:00'))
                    if continuing:
                        floor = max(floor, working.legs[-1]['departure_utc'])
                    try:
                        earliest = working.earliest(origin, destination, not_before=floor)
                    except ValueError as exc:
                        if 'REPOSITIONING_REQUIRED' not in str(exc):
                            raise
                        self.line(str(exc))
                        self.line(f'Positioning {labels[working.last_stop]} → {labels[origin]} costs money and carries no passengers.')
                        if self.prompt('Add positioning flight? [y/N]', allow_blank=True).strip().lower() not in {'y', 'yes'}:
                            continue
                        positioning = working.earliest(working.last_stop, origin, not_before=floor)
                        working.add(working.last_stop, origin, departure_utc=positioning, deadhead=True)
                        earliest = working.earliest(origin, destination, not_before=positioning)
                    self.line('Earliest departure: ' + parse_canonical_utc(earliest).astimezone(zone).strftime('%A %Y-%m-%d %H:%M:%S'))
                    if self.prompt('Use earliest departure? [Y/n]', allow_blank=True).strip().lower() in {'n', 'no'}:
                        day = int(ask('Day number Monday=1 through Sunday=7'))
                        if day not in range(1, 8):
                            raise ValueError('day must be 1 through 7')
                        departure = format_utc(local_departure(self.session.world['world_state'], origin,
                            (week + timedelta(days=day-1)).isoformat(), ask('Departure HH:MM')))
                    else:
                        departure = earliest
                    fare = parse_usd_fare(ask('Economy fare USD'))
                    working.add(origin, destination, departure_utc=departure, fare_minor=fare)
                    if self.prompt('Add earliest return? [y/N]', allow_blank=True).strip().lower() in {'y', 'yes'}:
                        working.add_return()
                    draft = working
                    self.line('Added to draft.')
                else:
                    self.line('Choose a listed action.')
            except (ValueError, KeyError, OverflowError) as exc:
                self.line(f'REJECTED: {exc}')

    def plan_rotation(self):
        aircraft = self.select_aircraft()
        if aircraft is None:
            return
        if aircraft['model_reference'] != 'A320-200':
            self.line('Quick Rotation is starter-only; use Weekly Scheduler.')
            return
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
                    f"cost {self.money(row['operating_cost_minor'])} "
                    f"(base {self.money(row['base_operating_cost_minor'])}, "
                    f"maintenance {self.money(row['maintenance_expense_minor'])}); "
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
        self.line(f"Aircraft assets: {self.money(view['aircraft_assets_minor'])}")
        self.line(f"Unflown-ticket liability: {self.money(view['unflown_ticket_liability_minor'])}")
        self.line(f"Passenger revenue: {self.money(view['passenger_revenue_minor'])}")
        self.line(f"Operating expenses: {self.money(view['operating_expenses_minor'])}")
        self.line(f"Cumulative fulfilment revenue: {self.money(view['cumulative_revenue_minor'])}")
        self.line(f"Cumulative fulfilment cost: {self.money(view['cumulative_cost_minor'])}")
        self.line(f"Cumulative operating contribution: {self.money(view['cumulative_profit_minor'])}")
        self.line(f"Recent results: {len(view['recent_results'])}; recent transactions: {len(view['recent_transactions'])}")
        for transaction in view['recent_transactions']:
            if transaction['source_type'] == 'AIRCRAFT_PURCHASE':
                self.line(f"{transaction['occurred_at_utc']} Aircraft purchase "
                          f"{transaction['source_id']}: {self.money(transaction['entries'][0]['amount_minor'])}")

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


def run_terminal(input_stream, output_stream, *, session_factory=Stage1Session,
                 input_source=None, handle_signals=False):
    """Run the harness using injected text streams and deterministic newlines."""
    terminal = None
    previous_signal = None
    try:
        terminal = _Terminal(input_stream, output_stream, session_factory(), input_source=input_source)
        if handle_signals:
            import signal
            previous_signal = signal.signal(signal.SIGINT,
                lambda *_: setattr(terminal, 'interrupt_requested', True))
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
    finally:
        if terminal is not None:
            terminal.session.close()
        if input_source is not None:
            input_source.close()
        if previous_signal is not None:
            import signal
            signal.signal(signal.SIGINT, previous_signal)


def main():
    if not sys.stdin.isatty():
        return run_terminal(sys.stdin, sys.stdout)
    from .input_queue import TerminalInput
    source = TerminalInput(sys.stdin)
    return run_terminal(sys.stdin, sys.stdout, input_source=source, handle_signals=True)


__all__ = ("main", "run_terminal")
