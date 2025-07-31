"""Dungeon crawler"""
import os
from dataclasses import dataclass, field


@dataclass
class World:
    w: int
    h: int

    def __post_init__(self):
        self.buffer = [" "] * (self.w * self.h)

    def clear(self):
        for i in range(self.w):
            for j in range(self.h):
                self.buffer[i + self.w * j] = "."

    def render(self, x, y, char):
        self.buffer[x + self.w * y] = char

    def draw(self):
        """Write buffer to screen"""
        for j in range(self.h):
            row = "".join(self.buffer[j*self.w:(j+1)*self.w])
            print(row)


class RenderSystem:
    def cls(self):
        os.system("clear")


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


@dataclass
class Game:
    world: World
    entities: list[Entity] = field(default_factory=list)

    def with_entity(self):
        entity = Entity()
        self.entities.append(entity)
        return entity

    def loop(self):
        self.world.clear()

        for position, renderable in self.iter_traits(Position, Renderable):
            self.world.render(position.x, position.y, renderable.char)

        self.world.draw()

    def iter_traits(self, *traits):
        for entity in self.entities:
            if entity.has(*traits):
                yield entity.get(*traits)


def main():
    game = Game(World(40, 30))

    graphics = RenderSystem()
    graphics.cls()


    # Wall
    for i in range(40):
        for j in [0, 29]:
            wall = game.with_entity() + Position(i, j) + Renderable("#")
    for i in [0, 39]:
        for j in range(30):
            wall = game.with_entity() + Position(i, j) + Renderable("#")

    # Player
    player = game.with_entity() + Player() + Position(20, 15) + Renderable("@")

    game.loop()


if __name__ == "__main__":
    main()
