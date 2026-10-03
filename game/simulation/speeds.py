"""PH player speed configuration; ratios are literal game seconds / real second.

Selected player speed is runtime-only. Saved kernel ratios are never interpreted
as relative multipliers, including when a legacy career is loaded.
"""
from dataclasses import dataclass

NORMAL_GAME_SECONDS_PER_REAL_SECOND = 30

@dataclass(frozen=True)
class PlayerSpeed:
    name: str
    relative_multiplier: int

    @property
    def ratio(self):
        return NORMAL_GAME_SECONDS_PER_REAL_SECOND * self.relative_multiplier

    @property
    def real_seconds_per_game_day(self):
        return 86400 / self.ratio

PLAYER_SPEEDS = (
    PlayerSpeed('Normal Speed', 1),
    PlayerSpeed('Fast', 7),
    PlayerSpeed('Very Fast', 30),
    PlayerSpeed('Ultra', 60),
)

def player_speed(name):
    for speed in PLAYER_SPEEDS:
        if speed.name == name:
            return speed
    raise ValueError(f'Unknown player speed: {name}')
