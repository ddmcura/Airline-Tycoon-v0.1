"""Small stable table shell for Airline Tycoon management pages."""
from math import isfinite
from decimal import Decimal
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from app.gui.scrolling import AxisScrollView


def cell(text, width):
    widget = Label(text=str(text), size_hint_x=None, width=dp(width), halign='left', valign='middle')
    widget.bind(size=lambda w, size: setattr(w, 'text_size', (size[0]-dp(10), size[1])))
    return widget


class ManagementTable(BoxLayout):
    """Fixed controls/header/footer; a single two-axis data viewport.

    Rows are detached presentation dictionaries. Search/sort/filter never writes
    world authority. Ordinary refresh reuses cells keyed by immutable entity ID.
    No page timer: the owning application refreshes only its active page.
    """
    def __init__(self, title, columns, *, search_fields, state=None, filters=(), actions=None, **kwargs):
        super().__init__(orientation='vertical', spacing=dp(4), **kwargs)
        self.state = dict(state or {})
        self.state.setdefault('query', ''); self.state.setdefault('filters', {})
        self.state.setdefault('sort', columns[0][0]); self.state.setdefault('descending', False)
        self.columns = columns; self.search_fields = search_fields; self.actions = actions or {}
        self.rows = []; self.visible_rows = []; self.cells = {}; self.row_widgets = {}
        self.data_updates = 0; self.closed = False
        self.heading = Label(text=title, size_hint_y=None, height=dp(42)); self.add_widget(self.heading)
        self.extra_controls = BoxLayout(orientation='vertical', size_hint_y=None, height=0)
        self.add_widget(self.extra_controls)
        self.controls = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(4))
        self.search = TextInput(text=self.state['query'], hint_text='Search', multiline=False, padding=(dp(10),dp(14)))
        self.search.bind(text=self._search); self.controls.add_widget(self.search)
        clear = Button(text='Clear / Reset', size_hint_x=None, width=dp(145))
        clear.bind(on_release=lambda *_: self.reset()); self.controls.add_widget(clear); self.add_widget(self.controls)
        self.filter_widgets = {}
        if filters:
            bar = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4))
            for key, caption in filters:
                widget = Spinner(text=self.state['filters'].get(key) or 'All '+caption)
                widget.bind(text=lambda w, text, k=key, c=caption: self._filter(k, c, text))
                self.filter_widgets[key] = (widget, caption); bar.add_widget(widget)
            self.add_widget(bar)
        self.table_width = dp(sum(c[2] for c in columns))
        self.header_scroll = AxisScrollView(size_hint_y=None, height=dp(48), do_scroll_y=False)
        header = BoxLayout(size_hint_x=None, width=self.table_width)
        self.header_buttons = {}
        for key, title, width in columns:
            button = Button(text=title, size_hint_x=None, width=dp(width))
            if key not in self.actions: button.bind(on_release=lambda _, k=key: self.sort_by(k))
            header.add_widget(button); self.header_buttons[key] = button
        self.header_scroll.add_widget(header); self.add_widget(self.header_scroll)
        self.viewport = AxisScrollView(do_scroll_x=True, do_scroll_y=True)
        self.body = BoxLayout(orientation='vertical', size_hint=(None,None), width=self.table_width, height=dp(52))
        self.viewport.add_widget(self.body); self.add_widget(self.viewport)
        self.viewport.bind(scroll_x=self._sync_header); self.header_scroll.bind(scroll_x=self._sync_body)
        self.footer = Label(text='', size_hint_y=None, height=dp(46)); self.add_widget(self.footer)
        self.viewport.scroll_x = self.state.get('scroll_x', 0)
        self.viewport.scroll_y = self.state.get('scroll_y', 1)
        self.apply()

    def _sync_header(self, _, value):
        if self.header_scroll.scroll_x != value: self.header_scroll.scroll_x = value

    def _sync_body(self, _, value):
        if self.viewport.scroll_x != value: self.viewport.scroll_x = value

    def _search(self, _, text):
        self.state['query'] = text; self.apply()

    def _filter(self, key, caption, text):
        self.state['filters'][key] = '' if text == 'All '+caption else text; self.apply()

    def reset(self):
        self.state['filters'] = {}; self.state['sort'] = self.columns[0][0]; self.state['descending'] = False
        self.search.text = ''
        for widget, caption in self.filter_widgets.values(): widget.text = 'All '+caption
        self.apply()

    def sort_by(self, key):
        self.state['descending'] = not self.state['descending'] if self.state['sort'] == key else False
        self.state['sort'] = key; self.apply()

    def set_rows(self, rows):
        # Derivation finished BEFORE replacing visible content. Identical rows do
        # no geometry/widget work, even when clock revisions change each pump.
        rows = [dict(row) for row in rows]
        if rows == self.rows: return
        self.rows = rows; self.data_updates += 1
        for key, (widget, caption) in self.filter_widgets.items():
            widget.values = tuple(['All '+caption] + sorted({str(row[key]) for row in rows if row.get(key) is not None}))
        self.apply()

    def apply(self):
        if self.closed: return
        query = self.state['query'].casefold().strip()
        rows = [r for r in self.rows if query in ' '.join(str(r.get(k) or '') for k in self.search_fields).casefold()
                and all(not value or str(r.get(key)) == value for key,value in self.state['filters'].items())]
        key = self.state['sort']
        # Stable identity breaks equal-column ties, independent of source order.
        rows.sort(key=lambda r: r['id'])
        rows.sort(key=lambda r: (r.get(key) is None, r.get(key) if isinstance(r.get(key), (int,float,Decimal)) else str(r.get(key) or '').casefold()), reverse=self.state['descending'])
        prepared = []
        for row in rows:
            identity = row['id']
            if identity not in self.row_widgets:
                line = BoxLayout(size_hint_y=None, height=dp(56), width=self.table_width)
                cells = {}
                for column, _, width in self.columns:
                    if column in self.actions:
                        w = Button(text=self.actions[column][0], size_hint_x=None, width=dp(width))
                        w.bind(on_release=lambda _, k=identity, c=column: self._act(c,k))
                    else: w = cell('', width)
                    cells[column] = w; line.add_widget(w)
                self.row_widgets[identity] = line; self.cells[identity] = cells
            for column, _, _ in self.columns:
                if column not in self.actions:
                    value = row.get(column+'_text', row.get(column))
                    self.cells[identity][column].text = str(value) if value is not None else '—'
            prepared.append(self.row_widgets[identity])
        keep = {r['id'] for r in self.rows}
        for identity in set(self.row_widgets)-keep:
            del self.row_widgets[identity]; del self.cells[identity]
        current = list(reversed(self.body.children))
        if current != prepared or self.body.height != dp(max(1,len(rows))*56):
            self.viewport.stop_motion(); self.header_scroll.stop_motion()
        # Height never passes through zero. Clear/reorder is synchronous, after
        # preparation, with an unchanged valid extent until final rows attach.
        self.body.height = dp(max(1,len(rows))*56)
        if current != prepared or not prepared:
            self.body.clear_widgets()
            if not prepared: self.body.add_widget(cell('No matching records', sum(c[2] for c in self.columns)))
            else:
                for line in prepared: self.body.add_widget(line)
        self.visible_rows = rows
        self.footer.text = f'{len(rows)} of {len(self.rows)} records'
        for column, _, _ in self.columns:
            caption = next(c[1] for c in self.columns if c[0]==column)
            self.header_buttons[column].text = caption + (' DESC' if self.state['descending'] else ' ASC') if column==key else caption

    def _act(self, column, identity):
        self.state['selected'] = identity
        row = next((r for r in self.rows if r['id']==identity), None)
        if row is not None: self.actions[column][1](row)

    def snapshot(self):
        return dict(self.state, filters=dict(self.state['filters']), scroll_x=self.viewport.scroll_x, scroll_y=self.viewport.scroll_y)

    def close(self):
        self.closed = True; self.viewport.dispose(); self.header_scroll.dispose()

    def finite(self):
        widgets = (self, self.body, self.viewport, self.header_scroll)
        values = [v for w in widgets for v in (*w.pos,*w.size)] + [self.viewport.scroll_x,self.viewport.scroll_y]
        values += [v for e in (self.viewport.effect_x,self.viewport.effect_y) for v in (e.value,e.velocity,e.min,e.max)]
        return all(isfinite(v) for v in values)
