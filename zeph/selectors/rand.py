"""Random selectors."""

from diamond_miner.typing import IPNetwork

from zeph.selectors.abstract import AbstractSelector


class RandomSelector(AbstractSelector):
    def select(self, agent_uuid: str) -> set[IPNetwork]:
        return self._select_random(agent_uuid)
