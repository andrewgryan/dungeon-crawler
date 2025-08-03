"""Dungeon crawler"""
from array import array
from dataclasses import dataclass, field
import curses
from curses import wrapper


@dataclass
class Position:
    x: int
    y: int


@dataclass
class Renderable:
    char: str = "@"
    color: int = curses.COLOR_BLUE


@dataclass
class Impassable:
    ...


@dataclass
class Player:
    ...


@dataclass
class Entity:
    components: dict[str, str] = field(default_factory=dict)

    def has(self, *traits):
        return all(trait in self.components for trait in traits)

    def get(self, *traits):
        return tuple(self.components[trait] for trait in traits)

    def __add__(self, component):
        return self.add(component)

    def add(self, component):
        self.components[component.__class__] = component
        return self

    def reset(self):
        # Convert to bare entity
        self.components = {}


class RenderSystem:
    def __init__(self, stdscr, width: int, height: int):
        self.stdscr = stdscr
        y, x = 2, 2
        self.window = curses.newwin(height + 1, width + 1, y, x)
        self.width = width
        self.height = height

        self._number = 1
        self._numbers = {}

    def erase(self):
        self.window.erase()

    def render(self, x, y, c, color):
        if color not in self._numbers:
            self._numbers[color] = self._number
            self._number += 1
        number = self._numbers[color]
        curses.init_pair(number, color, curses.COLOR_BLACK)
        self.window.addch(y, x, c, curses.color_pair(number))

    def refresh(self):
        self.window.refresh()
        self.stdscr.refresh()


@dataclass
class MovementSystem:
    width: int
    height: int

    def __post_init__(self):
        self.impassable_tiles = array("B", (0 for _ in range(self.width * self.height)))

    def cache_impassable(self, game):
        for _, position in game.iter_traits(Impassable, Position):
            i = position.x + self.width * position.y
            self.impassable_tiles[i] = 1

    def try_up(self, game):
        for _, position in game.iter_traits(Player, Position):
            x, y = position.x, position.y
            if y - 1 >= 0:
                y -= 1
            if self.passable(x, y):
                position.x, position.y = x, y

    def try_down(self, game):
        for _, position in game.iter_traits(Player, Position):
            x, y = position.x, position.y
            if y + 1 < self.height:
                y += 1
            if self.passable(x, y):
                position.x, position.y = x, y

    def try_left(self, game):
        for _, position in game.iter_traits(Player, Position):
            x, y = position.x, position.y
            if x - 1 >= 0:
                x -= 1
            if self.passable(x, y):
                position.x, position.y = x, y

    def try_right(self, game):
        for _, position in game.iter_traits(Player, Position):
            x, y = position.x, position.y
            if x + 1 < self.width:
                x += 1
            if self.passable(x, y):
                position.x, position.y = x, y

    def passable(self, x: int, y: int) -> bool:
        i = x + self.width * y
        return not bool(self.impassable_tiles[i])


@dataclass
class Game:
    render_system: RenderSystem
    entities: list[Entity] = field(default_factory=list)

    def with_entity(self):
        entity = Entity()
        self.entities.append(entity)
        return entity

    def loop(self):
        self.render_system.erase()
        for position, renderable in self.iter_traits(Position, Renderable):
            self.render_system.render(position.x, position.y, renderable.char, renderable.color)
        self.render_system.refresh()

    def iter_traits(self, *traits):
        for entity in self.entities:
            if entity.has(*traits):
                yield entity.get(*traits)

    def iter_entity_with_traits(self, *traits):
        for entity in self.entities:
            if entity.has(*traits):
                yield entity


@dataclass
class Room:
    x: int
    y: int
    width: int
    height: int

    @property
    def center(self):
        return self.x + (self.width // 2), self.y + (self.height // 2)


@dataclass
class Corridor:
    x0: int
    y0: int
    x1: int
    y1: int


@dataclass
class Level:
    rooms: list[Room]
    corridors: list[Corridor]


@dataclass
class MapSystem:
    screen_width: int
    screen_height: int

    def generate_level(self, game):
        atlas = [True] * (self.screen_width * self.screen_height)

        width, height = self.screen_width, self.screen_height
        room = Room(0, 0, width // 2, height // 2)
        for x in range(room.x, room.x + room.width):
            for y in range(room.y, room.y + room.height):
                atlas[x + self.screen_width * y] = False


        for x in range(0, self.screen_width):
            for y in range(0, self.screen_height):
                if atlas[x + self.screen_width * y]:
                    add_wall(game, x, y)

    def _generate_level(self, game):
        width, height = self.screen_width, self.screen_height
        rooms = [
            Room(0, 0, width // 2, 2 * height // 3),
            Room((width // 2) + 2, height // 3, (width // 2) - 4, height // 3)
        ]
        for room in rooms:
            self.generate_room(game, room)

        # Corridors
        x0, y0 = rooms[0].center
        x1, y1 = rooms[1].center
        corridor = Corridor(x0, y0, x1, y1)
        self.generate_corridor(game, corridor)

    def generate_room(self, game: Game, room: Room):
        x, y, width, height = room.x, room.y, room.width, room.height
        for i in range(x, x + width):
            for j in [y, y + height - 1]:
                add_wall(game, i, j)
        for i in [x, x + width - 1]:
            for j in range(y, y + height):
                add_wall(game, i, j)

    def generate_corridor(self, game: Game, corridor: Corridor):
        digging = False
        for x in range(corridor.x0, corridor.x1):
            if digging:
                self.place_wall(game, x, corridor.y0 + 1)
                self.place_wall(game, x, corridor.y0 - 1)

            # Check for walls
            for entity in game.iter_entity_with_traits(Position, Impassable, Renderable):
                position, = entity.get(Position)
                if (position.x, position.y) == (x, corridor.y0):
                    digging = not digging
                    entity.reset()

        for y in range(corridor.y0, corridor.y1):
            game.with_entity() + Position(corridor.x1, y) + Renderable(".")

    def place_wall(self, game, x, y):
        if not self.is_wall(game, x, y):
            game.with_entity() + Position(x, y) + Renderable("+") + Impassable()

    def is_wall(self, game, x, y):
        return any((position.x, position.y) == (x, y) for position, _, _ in game.iter_traits(Position, Impassable, Renderable))


def add_wall(game, i, j):
    return game.with_entity() + Position(i, j) + Renderable("#") + Impassable()


def main(stdscr):
    stdscr.clear()
    curses.curs_set(False)

    width = curses.COLS - 3
    height = curses.LINES - 3
    render_system = RenderSystem(stdscr, width=width, height=height)
    movement_system = MovementSystem(width=width, height=height)

    game = Game(render_system)

    map_system = MapSystem(screen_width=width, screen_height=height)
    map_system.generate_level(game)


    # Player
    player = game.with_entity() + Player() + Position(20, 15) + Renderable("@", curses.COLOR_GREEN)

    # Movement
    movement_system.cache_impassable(game)
    while True:
        key = stdscr.getkey()
        if key == "q":
            return
        elif key == "h":
            movement_system.try_left(game)
        elif key == "j":
            movement_system.try_down(game)
        elif key == "k":
            movement_system.try_up(game)
        elif key == "l":
            movement_system.try_right(game)
        game.loop()

    return


if __name__ == "__main__":
    wrapper(main)
