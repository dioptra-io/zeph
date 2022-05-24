from abc import ABC, abstractmethod

from zeph.typing import Agent, Link, Network


class AbstractRanker(ABC):
    @abstractmethod
    def __call__(
        self, links: dict[tuple[Agent, Network], set[Link]]
    ) -> dict[Agent, list[Network]]:
        ...
