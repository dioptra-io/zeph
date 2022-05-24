from collections import Counter, defaultdict

from diamond_miner.typing import IPNetwork

from zeph.rankers import AbstractRanker
from zeph.typing import Agent, Link


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
        rewards: dict[Agent, dict[IPNetwork, int]] = defaultdict(
            lambda: defaultdict(int)
        )
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
