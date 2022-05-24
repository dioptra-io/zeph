from abc import ABC, abstractmethod

from diamond_miner.typing import IPNetwork

from zeph.typing import Agent, Link


class AbstractRanker(ABC):
    @abstractmethod
    def __call__(
        self, links: dict[tuple[Agent, IPNetwork], set[Link]]
    ) -> dict[Agent, list[IPNetwork]]:
        """TODO"""
        ...
