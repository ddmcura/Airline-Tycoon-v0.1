"""Reusable Kivy airport picker over detached authoritative airport rows."""

from kivy.metrics import dp
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from app.gui.scrolling import AxisScrollView
from kivy.uix.textinput import TextInput


def airport_identity(row):
    # Before career creation, the curated reference code is the accepted input.
    return row.get("airport_id") or row["reference_code"]


def airport_label(row):
    return " — ".join(str(value) for value in (
        row.get("reference_code"), row.get("city"), row.get("display_name")) if value)


def matching_airports(airports, query):
    words = str(query).strip().casefold().split()
    return tuple(row for row in airports if all(
        word in " ".join(str(row.get(key) or "") for key in (
            "reference_code", "city", "display_name")).casefold()
        for word in words))


class AirportSelector(BoxLayout):
    """Searchable touch-sized picker; selection is UI state, never world state."""

    selected_id = StringProperty("")

    def __init__(self, airports, *, selected_id=None, allow_clear=False,
                 placeholder="Choose airport", **kwargs):
        super().__init__(orientation="vertical", size_hint_y=None, height=dp(54), **kwargs)
        self.airports = tuple(dict(row) for row in airports)
        self.allow_clear = allow_clear
        self.placeholder = placeholder
        self.popup = None
        self.button = Button(text=placeholder, size_hint_y=None, height=dp(52))
        self.button.bind(on_release=lambda *_: self.open_dropdown())
        self.add_widget(self.button)
        if selected_id is not None:
            self.select(selected_id)

    @property
    def text(self):
        return self.button.text

    def search(self, query):
        return matching_airports(self.airports, query)

    def select(self, identity):
        if identity in (None, "") and self.allow_clear:
            self.selected_id = ""
            self.button.text = self.placeholder
        else:
            row = next((row for row in self.airports
                        if airport_identity(row) == identity), None)
            if row is None:
                raise ValueError("choose a listed airport")
            self.selected_id = airport_identity(row)
            self.button.text = airport_label(row)
        if self.popup is not None:
            self.popup.dismiss()
            self.popup = None

    def open_dropdown(self):
        root = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(8))
        search = TextInput(hint_text="Search code, city or airport name",
                           multiline=False, size_hint_y=None, height=dp(52))
        root.add_widget(search)
        scroll = AxisScrollView(do_scroll_x=False)
        results = GridLayout(cols=1, spacing=dp(5), size_hint_y=None)
        results.bind(minimum_height=results.setter("height"))
        scroll.add_widget(results)
        root.add_widget(scroll)

        def update(_widget=None, query=""):
            results.clear_widgets()
            if self.allow_clear:
                clear = Button(text="All airports / clear selection",
                               size_hint_y=None, height=dp(52))
                clear.bind(on_release=lambda *_: self.select(None))
                results.add_widget(clear)
            matches = self.search(query)
            for row in matches:
                button = Button(text=airport_label(row), size_hint_y=None,
                                height=dp(58), halign="left")
                button.bind(on_release=lambda _button, identity=airport_identity(row):
                            self.select(identity))
                results.add_widget(button)
            if not matches:
                results.add_widget(Label(text="No matching airports",
                                         size_hint_y=None, height=dp(52)))

        search.bind(text=update)
        update(query="")
        self.popup = Popup(title="Choose airport", content=root, size_hint=(.94, .86),
                           auto_dismiss=True)
        self.popup.bind(on_dismiss=lambda *_: setattr(self, "popup", None))
        self.popup.open()
        return self.popup
