"""Dungeon crawler"""
import random
from enum import Enum
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
class Visible:
    ...


# TERRAIN

@dataclass
class Impassable:
    ...


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


# NON-PLAYER CHARACTERS

class Compass(Enum):
    N = 1
    S = 2
    E = 3
    W = 4


@dataclass
class PatrolBot:
    direction: Compass
    room: Room


@dataclass
class Player:
    health: int = 100


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

    def remove_trait(self, trait):
        del self.components[trait]
        return self

    def reset(self):
        # Convert to bare entity
        self.components = {}


# EQUIPMENT


@dataclass
class Item:
    label: str
    description: str = ""

    @classmethod
    def electro_mine(cls):
        return cls(label="Electro-mine",
                   description="Place in path of bots to fry their circuits. Careful, it can fry nearby circuits too.")

    @classmethod
    def glove(cls):
        return cls(label="Glove", description="A single glove")

    @classmethod
    def torch(cls):
        return cls(label="Torch", description="Useful in rooms without electric lights")


@dataclass
class Backpack:
    items: list[Item] = field(default_factory=list)


# SYSTEMS

@dataclass
class InventorySystem:
    def try_pick_up(self, game):
        # TODO: Think of the ECS way of picking up an item
        for player, backpack, player_position in game.iter_traits(Player, Backpack, Position):
            for item in game.iter_entities(Item, Position):
                item_position = item.get(Position)[0]
                if item_position == player_position:
                    item.remove_trait(Position)
                    backpack.items.append(item)


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
class AISystem:
    movement_system: MovementSystem

    def simulate(self, game, turns: int):
        """Simulate AI movement"""
        for _ in range(turns):
            self.run(game)

    def run(self, game):
        for bot, position in game.iter_traits(PatrolBot, Position):
            if bot.direction == Compass.E:
                if (position.x + 1) >= (bot.room.x + bot.room.width):
                    # Turn around
                    bot.direction = Compass.W
                    self.movement_system.try_left(position)
                else:
                    # Keep marching
                    self.movement_system.try_right(position)
            elif bot.direction == Compass.W:
                if (position.x - 1) <= bot.room.x:
                    # Turn around
                    bot.direction = Compass.E
                    self.movement_system.try_right(position)
                else:
                    # Keep marching
                    self.movement_system.try_left(position)
            elif bot.direction == Compass.N:
                if (position.y - 1) <= bot.room.y:
                    # Turn around
                    bot.direction = Compass.S
                    self.movement_system.try_down(position)
                else:
                    # Keep marching
                    self.movement_system.try_up(position)
            elif bot.direction == Compass.S:
                if (position.y + 1) >= (bot.room.y + bot.room.height):
                    # Turn around
                    bot.direction = Compass.N
                    self.movement_system.try_up(position)
                else:
                    # Keep marching
                    self.movement_system.try_down(position)



# GAME

@dataclass
class Game:
    entities: list[Entity] = field(default_factory=list)

    def with_entity(self):
        entity = Entity()
        self.entities.append(entity)
        return entity

    def iter_entities(self, *traits):
        for entity in self.entities:
            if entity.has(*traits):
                yield entity

    def iter_traits(self, *traits):
        for entity in self.iter_entities(*traits):
            yield entity.get(*traits)


@dataclass
class MapSystem:
    screen_width: int
    screen_height: int

    @property
    def rooms(self):
        # Carve out rooms
        width, height = self.screen_width, self.screen_height
        return [
            Room(1, 1, width // 2, height // 2),
            Room(1, 3 * (height // 4), width // 4, height // 4),
            Room(3 * (width // 4), 1, width // 4, height // 4),
            Room(2 * (width // 3), 2 * (height // 3) - 1, width // 3, height // 3)
        ]

    def generate_level(self, game):
        atlas = [True] * (self.screen_width * self.screen_height)

        # Rooms
        for room in self.rooms:
            for x in range(room.x, room.x + room.width):
                for y in range(room.y, room.y + room.height):
                    atlas[x + self.screen_width * y] = False

        # Connect rooms with corridors
        for a, b, x_then_y in [(0, 3, False), (2, 3, False)]:
            x0, y0 = self.rooms[a].center
            x1, y1 = self.rooms[b].center
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


class StatusBar:
    def __init__(self, stdscr):
        self.stdscr = stdscr

    def paint(self, game):
        for pl, in game.iter_traits(Player):
            self.stdscr.addstr(0, 0, f"health: {pl.health}")

class InventoryScreen:
    def __init__(self, stdscr):
        self.stdscr = stdscr

    def paint(self, game):
        for i, line in enumerate(self.lines(game)):
            self.stdscr.addstr(i, 0, line)

    def lines(self, game):
        for _, backpack in game.iter_traits(Player, Backpack):
            for i, item in enumerate(backpack.items):
                it, = item.get(Item)
                yield f"Item {i + 1}: {it.label} [{it.description}]"


def help_text(width: int): 
    text_wrapper = TextWrapper(width=width - 2)
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
    wrapped = [text_wrapper.fill(p) for p in paragraphs]
    lines = []
    for p in wrapped:
        lines += p.split("\n")
    return lines


class DialogSystem:
    def __init__(self, stdscr, dialog_open=False):
        self.stdscr = stdscr
        self.width = 40
        self.window = curses.newwin(curses.LINES, self.width, 0, curses.COLS - self.width)
        self.dialog_open = dialog_open
        self.scroll_index = 0

        # Content
        self.displayed_lines = []

    def toggle(self):
        self.dialog_open = not self.dialog_open

    def set_lines(self, lines: list[str]):
        self.displayed_lines = lines

    def paint(self):
        self.window.erase()
        if self.dialog_open:
            # Draw outline
            y0 = 0
            y1 = curses.LINES - 2
            x1 = self.width - 1 # curses.COLS - 2
            x0 = 0 # x1 - 40
            rectangle = curses.textpad.rectangle(self.window, y0, x0, y1, x1)

            # Write text
            for i, line in enumerate(self.displayed_lines[self.scroll_index:]):
                self.window.addstr(i + 1, x0 + 2, line)

    def scroll_up(self):
        if self.scroll_index - 1 > 0:
            self.scroll_index -= 1

    def scroll_down(self):
        if self.scroll_index + 1 < len(self.displayed_lines):
            self.scroll_index += 1

    def refresh(self):
        self.window.refresh()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="game", help="executable mode, 'game' or 'debug'")
    args = parser.parse_args()
    if args.mode == "game":
        wrapper(dungeon_crawler)
    else:
        print(f"'{args.mode}' mode not implemented")
    return


def dungeon_crawler(stdscr):
    # Main program
    stdscr.clear()
    curses.curs_set(False)

    # Configure screen
    width = curses.COLS
    height = curses.LINES
    render_system = RenderSystem(stdscr, width=width, height=height)
    movement_system = MovementSystem(width=width, height=height)
    ai_system = AISystem(movement_system)

    game = Game()

    map_system = MapSystem(screen_width=width, screen_height=height)
    map_system.generate_level(game)

    for room in map_system.rooms:
        x, y = room.center
        (game.with_entity()
         + PatrolBot(random.choice(list(Compass)), room)
         + Renderable("B", curses.COLOR_GREEN)
         + Position(x, y))

    # Narrator, inventory, etc.
    dialog_system = DialogSystem(stdscr)
    status = StatusBar(stdscr)

    inventory_system = InventorySystem()
    inventory_screen = InventoryScreen(stdscr)

    # Items
    item = (game.with_entity() +
            Item.electro_mine() +
            Position(22, 10) +
            Renderable("o") +
            Visible())

    # Player
    player = game.with_entity() + Player() + Backpack() + Position(20, 10) + Renderable("@", curses.COLOR_YELLOW) + Visible()
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
            status.paint(game)
            inventory_screen.paint(game)
            last_paint = current_time
        else:
            # Wait for render to complete
            continue


        # Handle user input
        key = stdscr.getkey()
        if key == "q":
            return
        elif key == "?":
            dialog_system.set_lines(help_text(dialog_system.width))
            dialog_system.toggle()
        elif key == "i":
            lines = list(inventory_screen.lines(game))
            dialog_system.set_lines(lines)
            dialog_system.toggle()

        if dialog_system.dialog_open:
            if key == "j":
                dialog_system.scroll_down()
            elif key == "k":
                dialog_system.scroll_up()
        else:
            # Human turn
            if key == "h":
                movement_system.try_left(player_position)
            elif key == "j":
                movement_system.try_down(player_position)
            elif key == "k":
                movement_system.try_up(player_position)
            elif key == "l":
                movement_system.try_right(player_position)
            elif key == "p":
                inventory_system.try_pick_up(game)

            # NPC turn
            if key in "hjkl":
                ai_system.run(game)

    return


# TESTS

def test_entity():
    game = Game()
    game.with_entity() + Player()
    assert len(list(game.iter_traits(Player))) == 1


def test_patrol_bot_ai_walking():
    game = Game()
    room = Room(0, 0, 5, 5)
    bot = game.with_entity() + PatrolBot(Compass.E, room) + Position(0, 0)
    movement_system = MovementSystem(width=10, height=10)
    ai_system = AISystem(movement_system)

    # Walk to edge of room
    ai_system.simulate(game, turns=4)
    assert bot.get(Position) == (Position(4, 0),)

    # Walk back
    ai_system.simulate(game, turns=1)
    assert bot.get(Position) == (Position(3, 0),)
    assert bot.get(PatrolBot) == (PatrolBot(Compass.W, room),)


def test_pick_up_item():
    game = Game()
    item = game.with_entity() + Item.glove() + Position(0, 0) + Renderable("i")
    player = game.with_entity() + Player() + Backpack() + Position(0, 0) + Renderable("@")

    inventory_system = InventorySystem()

    inventory_system.try_pick_up(game)
    assert item.has(Position) == False
    assert player.get(Backpack)[0].items == [item]


class FakeStdscr:
    called_with = None
    def addstr(self, x, y, s):
        self.called_with = (x, y, s)


def test_health_status():
    game = Game()
    stdscr = FakeStdscr()
    status = StatusBar(stdscr)
    player = game.with_entity() + Player(health=100)
    status.paint(game)
    assert stdscr.called_with == (0, 0, "health: 100")


def test_show_inventory():
    game = Game()
    stdscr = FakeStdscr()
    torch = game.with_entity() + Item.torch()
    player = game.with_entity() + Player() + Backpack(items=[torch])
    inventory = InventoryScreen(stdscr)
    inventory.paint(game)
    assert stdscr.called_with == (0, 0, "Item 1: Torch [Useful in rooms without electric lights]")


if __name__ == "__main__":
    main()
