"""Base for selectors."""

import random
from abc import ABC, abstractmethod

from zeph.typing import Network


class AbstractSelector(ABC):
    def __init__(self, universe: set[Network], budgets: dict[str, int]) -> None:
        self.universe = universe
        self.budgets = budgets

    def universe_shuffled(self) -> list[Network]:
        universe = list(self.universe)
        random.shuffle(universe)
        return universe

    @abstractmethod
    def select(self, agent_uuid: str) -> set[Network]:
        pass

    def _select_random(
        self, agent_uuid: str, preset: set[Network] | None = None
    ) -> set[Network]:
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
