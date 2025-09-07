import curses
from curses import wrapper
from dataclasses import dataclass


@dataclass
class Position:
    x: int
    y: int

    def __iter__(self):
        yield self.x
        yield self.y


@dataclass
class Backpack:
    ...

@dataclass
class NPC:
    ...

@dataclass
class Renderable:
    char: str

    def __iter__(self):
        yield self.char


@dataclass
class Viewable:
    opaque: bool = True


Component = Position | Renderable | Backpack | Viewable


class Game:
    entity: int = 0

    def __init__(self):
        self.store = {}

    def __add__(self, components: tuple[Component]):
        for component in components:
            try:
                self.store[component.__class__][self.entity] = component
            except KeyError:
                self.store[component.__class__] = {self.entity: component}

        self.entity += 1

    def iter_traits(self, *traits):
        entities = set.intersection(*tuple(set(self.store[trait].keys()) for trait in traits))
        for entity in entities:
            yield tuple(self.store[trait][entity] for trait in traits) 



def player(i, j):
    return (
        Position(i, j),
        Renderable("@"),
        Backpack(),
        Viewable()
    )

def bot(i, j):
    return (
        Position(i, j),
        Renderable("B"),
        NPC(),
        Viewable()
    )


def wall(i, j):
    return (
        Position(i, j),
        Renderable("#"),
        Viewable(opaque=True)
    )

def floor(i, j):
    return (
        Position(i, j),
        Renderable("."),
        Viewable(opaque=False)
    )




class RenderSystem:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.n_debug = 0

    def setup(self):
        curses.curs_set(False)
        self.stdscr.clear()
        return self

    def debug(self, obj):
        msg = str(obj)
        n_after = len(msg)
        n = max(self.n_debug, n_after)
        self.stdscr.addnstr(curses.LINES - 2, curses.COLS - n, msg.rjust(n), n)
        self.n_debug = n_after

    def run(self, game):
        for (x, y), (c,) in game.iter_traits(Position, Renderable):
            self.stdscr.addch(x, y, c)


def main(stdscr):
    render_system = RenderSystem(stdscr).setup()

    game = Game()
    n = 30
    for i in range(n):
        for j in range(n):
            if i == 0 or j == 0 or i == n - 1 or j == n - 1:
                game + wall(i, j)
            else:
                game + floor(i, j)
    game + player(0, 0)
    for i in range(4):
        game + bot(1 + 2 * i, i)

    render_system.run(game)
    keymap = {
        104: "h",
        106: "j",
        107: "k",
        108: "l",
        110: "n",
        113: "q",
        121: "y",
    }
    while True:
        c = stdscr.getch()
        if c == 113:
            render_system.debug("Are you sure? y/n")
            c = stdscr.getch()
            if c == 121:
                break
            elif c == 110:
                render_system.debug("")
        elif c in keymap:
            render_system.debug(keymap[c])
        else:
            render_system.debug(c)


if __name__ == '__main__':
    wrapper(main)
