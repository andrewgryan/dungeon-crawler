from enum import Enum
from dataclasses import dataclass, field


@dataclass
class Position:
    x: int
    y: int


class Luminosity(Enum):
    BRIGHT = 1
    DIM = 2
    HIDDEN = 3


@dataclass
class Viewable:
    opaque: bool = False
    luminosity: Luminosity = Luminosity.HIDDEN
    terrain: bool = False
