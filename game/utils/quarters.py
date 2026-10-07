"""Pure global UTC calendar quarters; unrelated to airport-local flight intent."""
from dataclasses import dataclass
from datetime import date, datetime, timezone
import re

from game.world_state.timestamps import parse_canonical_utc


@dataclass(frozen=True, order=True)
class Quarter:
    year: int
    number: int

    def __post_init__(self):
        if type(self.year) is not int or not 1 <= self.year <= 9999:
            raise ValueError('quarter year must be 1..9999')
        if type(self.number) is not int or not 1 <= self.number <= 4:
            raise ValueError('quarter number must be 1..4')

    @property
    def quarter_id(self):
        return f'{self.year:04d}-Q{self.number}'

    def shift(self, quarters=1):
        if type(quarters) is not int:
            raise ValueError('quarter offset must be an integer')
        year, number = divmod((self.year - 1) * 4 + self.number - 1 + quarters, 4)
        return Quarter(year + 1, number + 1)

    @property
    def start_utc(self):
        return datetime(self.year, (self.number - 1) * 3 + 1, 1, tzinfo=timezone.utc)

    @property
    def end_exclusive_utc(self):
        return self.shift().start_utc


def parse_quarter_id(value):
    if type(value) is not str or re.fullmatch(r'[0-9]{4}-Q[1-4]', value) is None:
        raise ValueError('quarter identity must be YYYY-Q1..YYYY-Q4')
    return Quarter(int(value[:4]), int(value[-1]))


def _utc_date(value):
    if type(value) is datetime:
        if value.tzinfo is None or value.utcoffset() is None or value.microsecond:
            raise ValueError('quarter timestamps must be aware whole seconds')
        return value.astimezone(timezone.utc).date()
    if type(value) is date:
        return value
    if type(value) is str and len(value) == 10:
        result = date.fromisoformat(value)
        if result.isoformat() != value:
            raise ValueError('date must be canonical YYYY-MM-DD')
        return result
    if type(value) is str:
        return parse_canonical_utc(value).date()
    raise ValueError('quarter input must be a UTC timestamp or calendar date')


def quarter_containing(value):
    day = _utc_date(value)
    return Quarter(day.year, (day.month - 1) // 3 + 1)


def normal_target_quarter(value):
    day = _utc_date(value)
    return quarter_containing(day).shift(2 if day.month % 3 == 0 else 1)
