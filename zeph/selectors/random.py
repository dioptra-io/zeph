"""Random selectors."""

from diamond_miner.typing import IPNetwork

from zeph.selectors.abstract import AbstractSelector


class RandomSelector(AbstractSelector):
    def select(
        self, agent_uuid: str, budget: int
    ) -> tuple[set[IPNetwork], set[IPNetwork]]:
        return set(), self._select_random(budget)
