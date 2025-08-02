"""Dungeon crawler"""
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


    def try_up(self, game):
        for _, position in game.iter_traits(Player, Position):
            x, y = position.x, position.y
            if y - 1 >= 0:
                y -= 1
            if self.passable(game, x, y):
                position.x, position.y = x, y

    def try_down(self, game):
        for _, position in game.iter_traits(Player, Position):
            x, y = position.x, position.y
            if y + 1 < self.height:
                y += 1
            if self.passable(game, x, y):
                position.x, position.y = x, y

    def try_left(self, game):
        for _, position in game.iter_traits(Player, Position):
            x, y = position.x, position.y
            if x - 1 >= 0:
                x -= 1
            if self.passable(game, x, y):
                position.x, position.y = x, y

    def try_right(self, game):
        for _, position in game.iter_traits(Player, Position):
            x, y = position.x, position.y
            if x + 1 < self.width:
                x += 1
            if self.passable(game, x, y):
                position.x, position.y = x, y

    def passable(self, game, x: int, y: int) -> bool:
        for _, position in game.iter_traits(Impassable, Position):
            if (position.x, position.y) == (x, y):
                return False
        return True


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


def main(stdscr):
    stdscr.clear()
    curses.curs_set(False)
    curses.init_pair(1, 0, curses.COLOR_BLACK)
    stdscr.addch(0, 0, "*", curses.color_pair(1))
    curses.init_pair(2, 1, curses.COLOR_BLACK)
    stdscr.addch(0, 1, "*", curses.color_pair(2))
    curses.init_pair(3, 2, curses.COLOR_BLACK)
    stdscr.addch(0, 2, "*", curses.color_pair(3))
    curses.init_pair(4, 3, curses.COLOR_BLACK)
    stdscr.addch(0, 3, "*", curses.color_pair(4))
    curses.init_pair(5, 4, curses.COLOR_BLACK)
    stdscr.addch(0, 4, "*", curses.color_pair(5))
    curses.init_pair(6, 5, curses.COLOR_BLACK)
    stdscr.addch(0, 5, "*", curses.color_pair(6))
    curses.init_pair(7, 6, curses.COLOR_BLACK)
    stdscr.addch(0, 6, "*", curses.color_pair(7))
    stdscr.getkey()

    render_system = RenderSystem(stdscr, width=40, height=30)
    movement_system = MovementSystem(width=40, height=30)

    game = Game(render_system)

    # Wall
    for i in range(40):
        for j in [0, 29]:
            wall = game.with_entity() + Position(i, j) + Renderable("#") + Impassable()
    for i in [0, 39]:
        for j in range(30):
            wall = game.with_entity() + Position(i, j) + Renderable("#") + Impassable()

    # Player
    player = game.with_entity() + Player() + Position(20, 15) + Renderable("@", curses.COLOR_GREEN)

    # Movement
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
