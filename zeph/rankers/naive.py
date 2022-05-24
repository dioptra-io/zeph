from collections import OrderedDict, defaultdict

from diamond_miner.typing import IPNetwork

from zeph.rankers import AbstractRanker
from zeph.typing import Agent, Link


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
