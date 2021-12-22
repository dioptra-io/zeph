"""Random selectors."""

from zeph.selectors.abstract import AbstractSelector


class RandomSelector(AbstractSelector):
    def select(self, agent_uuid, budget: int):
        return self._select_random(agent_uuid, budget)
