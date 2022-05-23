from abc import ABC, abstractmethod
from collections import Counter, OrderedDict, defaultdict

from diamond_miner.typing import IPNetwork

from zeph.typing import Agent, Link


class AbstractRanker(ABC):
    @abstractmethod
    def __call__(
        self, links: dict[tuple[Agent, IPNetwork], set[Link]]
    ) -> dict[Agent, list[IPNetwork]]:
        """TODO"""
        ...


class DFGCoverRanker(AbstractRanker):
    """
    TODO: Ref + explanation p.
    """

    def __init__(self, p: float = 1.05):
        self.p = p

    def __call__(
        self, links: dict[tuple[Agent, IPNetwork], set[Link]]
    ) -> dict[Agent, list[IPNetwork]]:
        covered: set[tuple[str, str]] = set()
        prefixes = defaultdict(list)
        subcollections = defaultdict(list)

        # Populate the sub-collections
        for (agent, prefix), links_ in links.items():
            k = 0
            while self.p ** (k + 1) < len(links_):
                k += 1
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
                    k_prime = 0
                    while self.p ** (k_prime + 1) < len(links[(agent, prefix)]):
                        k_prime += 1
                    subcollections[k_prime].append((agent, prefix))

        # k = 0
        for (agent, prefix) in subcollections[0]:
            if len(links[(agent, prefix)] - covered) == 1:
                prefixes[agent].append(prefix)
                covered.update(links[(agent, prefix)])

        return prefixes


class GreedyCoverRanker(AbstractRanker):
    def __call__(
        self, links: dict[tuple[Agent, IPNetwork], set[Link]]
    ) -> dict[Agent, list[IPNetwork]]:
        all_links: set[Link] = set()
        covered: set[tuple[str, str]] = set()
        prefixes: dict[Agent, list[IPNetwork]] = defaultdict(list)

        for links_ in links.values():
            all_links.update(links_)

        while covered != all_links and links:
            agent, prefix = max(links, key=lambda k: len(links[k] - covered))
            prefixes[agent].append(prefix)
            covered.update(links[(agent, prefix)])
            links.pop((agent, prefix))

        return prefixes


class NaiveRanker(AbstractRanker):
    def __call__(
        self, links: dict[tuple[Agent, IPNetwork], set[Link]]
    ) -> dict[Agent, list[IPNetwork]]:
        all_links: set[Link] = set()
        covered: set[tuple[str, str]] = set()
        prefixes: dict[Agent, list[IPNetwork]] = defaultdict(list)

        for links_ in links.values():
            all_links.update(links_)

        # Sort the subsets by size in descending order
        subsets = OrderedDict(
            sorted(
                [(k, v) for k, v in links.items()],
                key=lambda x: len(x[1]),
                reverse=True,
            )
        )

        for agent, prefix in subsets:
            if covered == all_links:
                break
            if subsets[(agent, prefix)] - covered:
                prefixes[agent].append(prefix)
                covered.update(subsets[(agent, prefix)])

        return prefixes


class UniqueLinksRanker(AbstractRanker):
    def __call__(
        self, links: dict[tuple[Agent, IPNetwork], set[Link]]
    ) -> dict[Agent, list[IPNetwork]]:
        """
        links: (agent, prefix) -> links
        """
        # Count how many times each link has been seen
        counts: Counter[Link] = Counter()
        for links_ in links.values():
            counts.update(links_)

        # Compute the reward as the number of globally unique (across all agents) links a prefix has seen.
        rewards: dict[Agent, dict[IPNetwork, int]] = defaultdict(dict)
        for (agent, prefix), links_ in links.items():
            for link in links_:
                if counts[link] == 1:
                    rewards[agent][prefix] += 1

        # Sort the prefixes by reward
        prefixes: dict[Agent, list[IPNetwork]] = {}
        for agent, rewards_ in rewards.items():
            prefixes[agent] = [
                x[0] for x in sorted(rewards_.items(), key=lambda x: x[1])
            ]

        return prefixes
