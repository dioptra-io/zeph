"""Random selectors."""


from zeph.selectors.abstract import AbstractSelector
from zeph.typing import Network


class RandomSelector(AbstractSelector):
    def select(self, agent_uuid: str) -> set[Network]:
        return self._select_random(agent_uuid)
