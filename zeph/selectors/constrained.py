"""
Constrained selectors.

Add the constraint of a prefix being probed by exactly one agent.
It's less effective than letting the agents potentially probe the same prefixes (see paper).
"""

from collections import defaultdict
from itertools import cycle

from zeph.selectors.random import RandomSelector
from zeph.typing import Network


class ConstrainedRandomSelector(RandomSelector):
    def __init__(self, universe: set[Network], budgets: dict[str, int]) -> None:
        super().__init__(universe, budgets)
        self.prefixes = self.dispatch()

    def dispatch(self) -> dict[str, set[Network]]:
        prefixes: dict[str, set[Network]] = defaultdict(set)
        for agent, prefix in zip(cycle(self.budgets), self.universe_shuffled()):
            if len(prefixes[agent]) >= self.budgets[agent]:
                continue
            prefixes[agent].add(prefix)
        return prefixes

    def select(self, agent_uuid: str) -> set[Network]:
        return self.prefixes[agent_uuid]
