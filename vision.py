import curses
from dataclasses import dataclass, field
from components import (
    Luminosity,
    Player,
    Position,
    Viewable
)


@dataclass
class VisionSystem:
    seen: list[Viewable] = field(default_factory=list)

    def run(self, game):
        self.run_shadow_casting(game)

    @staticmethod
    def get_player_position(game):
        x, y = None, None
        for position, _, _ in game.iter_traits(Position, Player, Viewable):
            x, y = position.x, position.y
            break
        return x, y

    def dim_seen_viewables(self):
        for viewable in self.seen:
            if viewable.luminosity == Luminosity.BRIGHT:
                viewable.luminosity = Luminosity.DIM if viewable.terrain else Luminosity.HIDDEN

    def run_shadow_casting(self, game):
        x, y = self.get_player_position(game)

        # Dim previously bright viewables
        self.dim_seen_viewables()

        self.seen = self.run_algorithm(x, y, game)

        # Illuminate seen viewables
        for viewable in self.seen: 
            viewable.luminosity = Luminosity.BRIGHT

    def run_algorithm(self, x, y, game):
        viewables = Viewables.from_game(game)

        # OCTANT 1-8
        seen = []
        seen += scan(1, x, y, viewables)
        seen += scan(2, x, y, viewables)
        seen += scan(3, x, y, viewables)
        seen += scan(4, x, y, viewables)
        seen += scan(5, x, y, viewables)
        seen += scan(6, x, y, viewables)
        seen += scan(7, x, y, viewables)
        seen += scan(8, x, y, viewables)
        return seen

    def run_square_viewshed(self, game, viewshed_range=5):
        for _, player_position, viewable in game.iter_traits(Player, Position, Viewable):
            viewable.luminosity = Luminosity.BRIGHT
            player_x, player_y = player_position.x, player_position.y
            for position, viewable in game.iter_traits(Position, Viewable):
                if (abs(position.x - player_x) <= viewshed_range) and (abs(position.y - player_y) <= viewshed_range):
                    viewable.luminosity = Luminosity.BRIGHT
                else:
                    if not viewable.terrain:
                        viewable.luminosity = Luminosity.HIDDEN
                    elif viewable.luminosity == Luminosity.BRIGHT:
                        viewable.luminosity = Luminosity.DIM

# SHADOW CASTING
class Viewables:
    """Simulate a sparse array interface to Viewable entities with Position"""
    def __init__(self, kvs: dict[tuple[int, int], list[Viewable]], default_factory = list):
        self.kvs = kvs
        self.default_factory = default_factory

    def __getitem__(self, key):
        return self.kvs.get(key, self.default_factory())

    @classmethod
    def from_game(cls, game):
        vs: dict[tuple[int, int], list[Viewable]] = {}
        for position, viewable in game.iter_traits(Position, Viewable):
            key = (position.x, position.y)
            try:
                vs[key].append(viewable)
            except KeyError:
                vs[key] = [viewable]
        return cls(vs)


def screen_bounds(x: int, y: int) -> bool:
    return (x < 0) | (y < 0) | (x >= curses.COLS) | (y >= curses.LINES)


def scan(octant: int, x: int, y: int, viewables: Viewables, slope_range=None, bounds_check=screen_bounds) -> list[Viewable]:
    # TODO: Separate scan start from light source origin
    seen = []
    wall_seen = False
    for i, j in iter_octant(octant):
        if bounds_check(x + i, y + j):
            break

        # Limit scan to between two rays
        if slope_range is not None:
            a, b = (x, y), (x + i, y + j)
            if octant in (1, 2, 5, 6):
                m = inverse_slope(a, b)
            elif octant in (3, 4, 7, 8):
                m = slope(a, b)
            if (m < slope_range[0]) or (m > slope_range[1]):
                continue

        # Gather viewables in lit area
        for viewable in viewables[x + i, y + j]:
            seen.append(viewable)

        # TODO: Recursive scan when wall/opening encountered
        wall = any(viewable.opaque for viewable in viewables[x + i, y + j])
        if wall and octant == 1:
            slope_range = (0, 0.5)
            seen += scan(octant, x + i - 1, y + j, viewables, slope_range=slope_range, bounds_check=bounds_check)

        wall_seen = wall_seen | wall
        if octant in (1, 2, 5, 6):
            if i == 0 and wall_seen:
                break
        elif octant in (3, 4, 7, 8):
            if j == 0 and wall_seen:
                break
    return seen


def test_scan():
    octant = 1
    x, y = 0, 0
    viewables = {
        (-2, 3): [Viewable()],
        (-1, 3): [Viewable()],
        (0, 3): [Viewable()],
        (-2, 2): [],
        (-1, 2): [Viewable()],
        (0, 2): [],
        (-1, 1): [Viewable(opaque=True)],
        (0, 1): [],
    }
    bounds_check = lambda x, y: (y > 3)
    actual = scan(octant, x, y, viewables, bounds_check=bounds_check)
    expected = viewables[-1, 1]
    assert actual == expected


def test_viewables_lookup_table():
    game = Game()
    traits = [Viewable(terrain=True), Viewable()]
    for viewable in traits:
        entity = game.with_entity() + Position(1, 0) + viewable
    actual = Viewables.from_game(game)
    assert actual[1, 0] == traits
    assert actual[0, 0] == []


def iter_octant(index: int):
    r"""Custom-iterator for shadow casting algorithm

    Octant indices work like this.

    \111|222/
    8\11|22/3
    88\1|2/33
    888\|/333
    ----@----
    777/|\444
    77/6|5\44
    7/66|55\4
    /666|555\

    """
    k = 1
    while True:
        if index == 1:
            yield from ((-i, k) for i in reversed(range(k + 1)))
        elif index == 2:
            yield from ((i, k) for i in reversed(range(k + 1)))
        elif index == 3:
            yield from ((k, i) for i in reversed(range(k + 1)))
        elif index == 4:
            yield from ((k, -i) for i in reversed(range(k + 1)))
        elif index == 5:
            yield from ((i, -k) for i in reversed(range(k + 1)))
        elif index == 6:
            yield from ((-i, -k) for i in reversed(range(k + 1)))
        elif index == 7:
            yield from ((-k, -i) for i in reversed(range(k + 1)))
        elif index == 8:
            yield from ((-k, i) for i in reversed(range(k + 1)))
        else:
            break
        k += 1


def test_vision_system_shadow_casting():
    # Octant iterator
    iterator = iter_octant(1)
    assert next(iterator) == (-1, 1)
    assert next(iterator) == (0, 1)
    assert next(iterator) == (-2, 2)
    assert next(iterator) == (-1, 2)
    assert next(iterator) == (0, 2)

    iterator = iter_octant(2)
    assert next(iterator) == (1, 1)
    assert next(iterator) == (0, 1)
    assert next(iterator) == (2, 2)
    assert next(iterator) == (1, 2)
    assert next(iterator) == (0, 2)

    iterator = iter_octant(3)
    assert next(iterator) == (1, 1)
    assert next(iterator) == (1, 0)
    assert next(iterator) == (2, 2)
    assert next(iterator) == (2, 1)
    assert next(iterator) == (2, 0)

    iterator = iter_octant(4)
    assert next(iterator) == (1, -1)
    assert next(iterator) == (1, 0)
    assert next(iterator) == (2, -2)
    assert next(iterator) == (2, -1)
    assert next(iterator) == (2, 0)

    iterator = iter_octant(5)
    assert next(iterator) == (1, -1)
    assert next(iterator) == (0, -1)
    assert next(iterator) == (2, -2)
    assert next(iterator) == (1, -2)
    assert next(iterator) == (0, -2)

    iterator = iter_octant(6)
    assert next(iterator) == (-1, -1)
    assert next(iterator) == (0, -1)
    assert next(iterator) == (-2, -2)
    assert next(iterator) == (-1, -2)
    assert next(iterator) == (0, -2)

    iterator = iter_octant(7)
    assert next(iterator) == (-1, -1)
    assert next(iterator) == (-1, 0)
    assert next(iterator) == (-2, -2)
    assert next(iterator) == (-2, -1)
    assert next(iterator) == (-2, 0)

    iterator = iter_octant(8)
    assert next(iterator) == (-1, 1)
    assert next(iterator) == (-1, 0)
    assert next(iterator) == (-2, 2)
    assert next(iterator) == (-2, 1)
    assert next(iterator) == (-2, 0)


def inverse_slope(a: tuple[int, int], b: tuple[int, int]) -> float:
    (x1, y1), (x2, y2) = a, b
    if y1 == y2:
        return float("inf")
    return (x2 - x1) / (y2 - y1)


def slope(a: tuple[int, int], b: tuple[int, int]) -> float:
    (x1, y1), (x2, y2) = a, b
    if x1 == x2:
        return float("inf")
    return (y2 - y1) / (x2 - x1)


def test_slope():
    assert slope((0, 0), (1, 1)) == 1.0
    assert slope((0, 0), (1, 0)) == 0.0
    assert slope((0, 0), (0.1, 1)) == 10.0


def test_inverse_slope():
    assert inverse_slope((0, 0), (-1, 1)) == -1.0
    assert inverse_slope((0, 0), (1, 1)) == 1.0
    assert inverse_slope((0, 0), (0, 1)) == 0.0
    assert inverse_slope((0, 0), (0, -1)) == 0.0
    assert inverse_slope((0, 0), (1, -1)) == -1.0
    assert inverse_slope((0, 0), (-1, -1)) == 1.0

