from dataclasses import dataclass, field


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

    def iter_by_component(self, component):
        for entity in self.iter_entities(component.__class__):
            if entity.components[component.__class__] == component:
                yield entity


