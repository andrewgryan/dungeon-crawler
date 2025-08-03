"""Dungeon crawler"""
from textwrap import TextWrapper
import argparse
from datetime import datetime, timedelta
from array import array
from dataclasses import dataclass, field
import curses
import curses.ascii
import curses.textpad

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
        y, x = 0, 0
        self.window = curses.newwin(height + 1, width + 1, y, x)
        self.width = width
        self.height = height

        self._number = 1
        self._numbers = {}

    def paint(self, game):
        self.erase()
        for position, renderable in game.iter_traits(Position, Renderable):
            self.render(position.x, position.y, renderable.char, renderable.color)
        self.refresh()

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
        # self.stdscr.refresh()


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

    def try_up(self, position):
        x, y = position.x, position.y
        if y - 1 >= 0:
            y -= 1
        if self.passable(x, y):
            position.x, position.y = x, y

    def try_down(self, position):
        x, y = position.x, position.y
        if y + 1 < self.height:
            y += 1
        if self.passable(x, y):
            position.x, position.y = x, y

    def try_left(self, position):
        x, y = position.x, position.y
        if x - 1 >= 0:
            x -= 1
        if self.passable(x, y):
            position.x, position.y = x, y

    def try_right(self, position):
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
    entities: list[Entity] = field(default_factory=list)

    def with_entity(self):
        entity = Entity()
        self.entities.append(entity)
        return entity

    def iter_traits(self, *traits):
        for entity in self.entities:
            if entity.has(*traits):
                yield entity.get(*traits)


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

        # Carve out rooms
        rooms = [
            Room(1, 1, width // 2, height // 2),
            Room(1, 3 * (height // 4), width // 4, height // 4),
            Room(3 * (width // 4), 1, width // 4, height // 4),
            Room(2 * (width // 3), 2 * (height // 3) - 1, width // 3, height // 3)
        ]

        for room in rooms:
            for x in range(room.x, room.x + room.width):
                for y in range(room.y, room.y + room.height):
                    atlas[x + self.screen_width * y] = False

        # Connect rooms with corridors
        for a, b, x_then_y in [(0, 3, False), (2, 3, False)]:
            x0, y0 = rooms[a].center
            x1, y1 = rooms[b].center
            corridor = Corridor(x0, y0, x1, y1)
            if x_then_y:
                for x in range(corridor.x0, corridor.x1):
                    atlas[x + self.screen_width * corridor.y0] = False
                for y in range(corridor.y0, corridor.y1):
                    atlas[corridor.x1 + self.screen_width * y] = False
            else:
                for y in range(corridor.y0, corridor.y1):
                    x = corridor.x0
                    atlas[x + self.screen_width * y] = False
                    atlas[x + 1 + self.screen_width * y] = False
                for x in range(corridor.x0, corridor.x1):
                    y = corridor.y1
                    atlas[x + self.screen_width * y] = False
                    atlas[x + self.screen_width * (y + 1)] = False

        # Place wall tiles
        for x in range(0, self.screen_width):
            for y in range(0, self.screen_height):
                if atlas[x + self.screen_width * y]:
                    game.with_entity() + Position(x, y) + Renderable("#") + Impassable()

    def is_wall(self, game, x, y):
        return any((position.x, position.y) == (x, y) for position, _, _ in game.iter_traits(Position, Impassable, Renderable))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="game", help="executable mode, 'game' or 'debug'")
    args = parser.parse_args()
    if args.mode == "game":
        wrapper(dungeon_crawler)
    else:
        wrapper(debug)
    return


class DialogSystem:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.text_wrapper = TextWrapper(width=38)
        self.window = curses.newwin(curses.LINES, curses.COLS, 0, 0)
        self.dialog_open = True
        self.scroll_index = 0

        # Content
        paragraphs = [
            "Greetings, Traveller!",
            "",
            "Welcome to Dungeon Crawler! The underground realm is all we have now, since the overworld fell."
            "",
            "",
            "Exploration is the name of the game. Survive by your wits. Accumulate technology to help you on your way."
            "",
            "",
            "And most importantly, trust no one."
            "",
            "",
            "press '?' to toggle dialog",
            "use 'j' and 'k' to scroll dialog",
        ]
        wrapped = [self.text_wrapper.fill(p) for p in paragraphs]
        lines = []
        for p in wrapped:
            lines += p.split("\n")
        self.displayed_lines = lines

    def toggle(self):
        self.dialog_open = not self.dialog_open

    def paint(self):
        if self.dialog_open:
            self.window.erase()
            # Draw outline
            y0 = 0
            y1 = curses.LINES - 2
            x1 = curses.COLS - 2
            x0 = x1 - 40
            rectangle = curses.textpad.rectangle(self.window, y0, x0, y1, x1)

            # Write text
            for i, line in enumerate(self.displayed_lines[self.scroll_index:]):
                self.window.addstr(i + 1, x0 + 2, line)
        else:
            self.window.erase()

    def scroll_up(self):
        if self.scroll_index - 1 > 0:
            self.scroll_index -= 1

    def scroll_down(self):
        if self.scroll_index + 1 < len(self.displayed_lines):
            self.scroll_index += 1

    def refresh(self):
        self.window.refresh()


def debug(stdscr):
    # Interactive systems development
    stdscr.clear()
    window = curses.newwin(curses.LINES, curses.COLS, 0, 0)
    window.refresh()
    stdscr.refresh()

    dialog_system = DialogSystem(stdscr)

    while True:
        dialog_system.paint()
        dialog_system.refresh()
        stdscr.refresh()
        key = stdscr.getch()
        if key == ord("q"):
            return
        elif key == ord("?"):
            dialog_system.toggle()
        elif key == ord("j"):
            dialog_system.scroll_down()
        elif key == ord("k"):
            dialog_system.scroll_up()


def dungeon_crawler(stdscr):
    # Main program
    stdscr.clear()
    curses.curs_set(False)

    width = curses.COLS
    height = curses.LINES
    render_system = RenderSystem(stdscr, width=width, height=height)
    movement_system = MovementSystem(width=width, height=height)

    game = Game()

    map_system = MapSystem(screen_width=width, screen_height=height)
    map_system.generate_level(game)

    # Narrator, inventory, etc.
    dialog_system = DialogSystem(stdscr)

    # Player
    player = game.with_entity() + Player() + Position(20, 10) + Renderable("@", curses.COLOR_GREEN)
    player_position, = player.get(Position)

    # Movement
    movement_system.cache_impassable(game)
    render_system.paint(game)
    last_paint = datetime.now()
    refresh_rate = timedelta(microseconds=16.7 * 1000)
    while True:

        # Throttle render system
        current_time = datetime.now()
        time_since_paint = current_time - last_paint
        if time_since_paint > refresh_rate:
            # Dialog is in the top-layer
            if dialog_system.dialog_open:
                dialog_system.paint()
                dialog_system.refresh()
            else:
                render_system.paint(game)
            last_paint = current_time
        else:
            # Wait for render to complete
            continue


        # Handle user input
        key = stdscr.getkey()
        if key == "q":
            return
        elif key == "?":
            dialog_system.toggle()

        if dialog_system.dialog_open:
            if key == "j":
                dialog_system.scroll_down()
            elif key == "k":
                dialog_system.scroll_up()
        else:
            if key == "h":
                movement_system.try_left(player_position)
            elif key == "j":
                movement_system.try_down(player_position)
            elif key == "k":
                movement_system.try_up(player_position)
            elif key == "l":
                movement_system.try_right(player_position)

    return


if __name__ == "__main__":
    main()
