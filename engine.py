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

    def erase(self):
        self.window.erase()

    def render(self, x, y, c):
        self.window.addch(y, x, c)

    def refresh(self):
        self.window.refresh()
        self.stdscr.refresh()


@dataclass
class MovementSystem:
    width: int
    height: int

    def try_up(self, game):
        for _, position in game.iter_traits(Player, Position):
            if position.y - 1 >= 0:
                position.y -= 1

    def try_down(self, game):
        for _, position in game.iter_traits(Player, Position):
            if position.y + 1 < self.height:
                position.y += 1

    def try_left(self, game):
        for _, position in game.iter_traits(Player, Position):
            if position.x - 1 >= 0:
                position.x -= 1

    def try_right(self, game):
        for _, position in game.iter_traits(Player, Position):
            if position.x + 1 < self.width:
                position.x += 1


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
            self.render_system.render(position.x, position.y, renderable.char)
        self.render_system.refresh()

    def iter_traits(self, *traits):
        for entity in self.entities:
            if entity.has(*traits):
                yield entity.get(*traits)


def main(stdscr):
    stdscr.clear()
    curses.curs_set(False)
    render_system = RenderSystem(stdscr, width=40, height=30)
    movement_system = MovementSystem(width=40, height=30)

    game = Game(render_system)

    # Wall
    for i in range(40):
        for j in [0, 29]:
            wall = game.with_entity() + Position(i, j) + Renderable("#")
    for i in [0, 39]:
        for j in range(30):
            wall = game.with_entity() + Position(i, j) + Renderable("#")

    # Player
    player = game.with_entity() + Player() + Position(20, 15) + Renderable("@")

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
