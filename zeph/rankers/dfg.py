from collections import defaultdict
from math import floor, log

from zeph.rankers import AbstractRanker
from zeph.typing import Agent, Link, Network


class DFGCoverRanker(AbstractRanker):
    """
    Reference:
    Cormode, Graham, Howard Karloff, and Anthony Wirth.
    "Set cover algorithms for very large datasets."
    Proceedings of the 19th ACM international conference on Information and knowledge management. 2010.
    """

    def __init__(self, p: float = 1.05):
        self.p = p

    def __call__(
        self, links: dict[tuple[Agent, Network], set[Link]]
    ) -> dict[Agent, list[Network]]:
        if not links:
            return {}

        covered: set[Link] = set()
        prefixes = defaultdict(list)
        subcollections = defaultdict(list)

        # Populate the sub-collections
        for (agent, prefix), links_ in links.items():
            k = floor(log(len(links_) or 1, self.p))
            subcollections[k].append((agent, prefix))
        k_max = max(subcollections.keys())

        # k = k_max ... 1
        for k in range(k_max, 0, -1):
            for (agent, prefix) in subcollections[k]:
                if len(links[(agent, prefix)] - covered) >= self.p**k:
                    prefixes[agent].append(prefix)
                    covered.update(links[(agent, prefix)])
                else:
                    links[(agent, prefix)] -= covered
                    k_prime = floor(log(len(links[(agent, prefix)]) or 1, self.p))
                    subcollections[k_prime].append((agent, prefix))

        # k = 0
        for (agent, prefix) in subcollections[0]:
            if len(links[(agent, prefix)] - covered) == 1:
                prefixes[agent].append(prefix)
                covered.update(links[(agent, prefix)])

        return prefixes
