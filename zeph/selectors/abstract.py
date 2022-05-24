"""Base for selectors."""

import random
from abc import ABC, abstractmethod

from diamond_miner.typing import IPNetwork


class AbstractSelector(ABC):
    def __init__(self, universe: set[IPNetwork], budgets: dict[str, int]) -> None:
        # TODO: Document: a list of /24 prefixes
        # TODO: Check that this is actually a list of /24 + todo IPv6 support
        # TODO: Default universe? Lazily generate /24?
        self.universe = universe
        self.budgets = budgets

    def universe_shuffled(self) -> list[IPNetwork]:
        universe = list(self.universe)
        random.shuffle(universe)
        return universe

    @abstractmethod
    def select(self, agent_uuid: str) -> set[IPNetwork]:
        pass

    def _select_random(
        self, agent_uuid: str, preset: set[IPNetwork] | None = None
    ) -> set[IPNetwork]:
        prefixes = set()
        if preset:
            prefixes.update(preset)
        universe = self.universe_shuffled()
        budget = self.budgets[agent_uuid]
        for prefix in universe:
            if len(prefixes) >= budget:
                break
            prefixes.add(prefix)
        return prefixes
