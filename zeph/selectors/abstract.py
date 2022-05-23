"""Base for selectors."""

import random
from abc import ABC, abstractmethod

from diamond_miner.typing import IPNetwork


class AbstractSelector(ABC):
    def __init__(self, universe: set[IPNetwork]) -> None:
        # TODO: Document: a list of /24 prefixes
        # TODO: Check that this is actually a list of /24 + todo IPv6 support
        # TODO: Default universe? Lazily generate /24?
        self.universe = universe

    def universe_shuffled(self) -> list[IPNetwork]:
        universe = list(self.universe)
        random.shuffle(universe)
        return universe

    @abstractmethod
    def select(
        self, agent_uuid: str, budget: int
    ) -> tuple[set[IPNetwork], set[IPNetwork]]:
        pass

    def _select_random(
        self, budget: int, preset: set[IPNetwork] | None = None
    ) -> set[IPNetwork]:
        preset = preset or set()
        universe = self.universe_shuffled()
        while len(preset) < min(len(universe), budget):
            preset.add(universe.pop())
        return preset
