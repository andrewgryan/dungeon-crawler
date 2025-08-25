from dataclasses import dataclass
from components import Viewable, Position


@dataclass
class Tile:
    viewables: list[Viewable]

    @property
    def opaque(self):
        return any(
            viewable.opaque
            for viewable in self.viewables
        )


TileArray = dict[Position, Tile]
