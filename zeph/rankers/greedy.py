from collections import defaultdict

from diamond_miner.typing import IPNetwork

from zeph.rankers import AbstractRanker
from zeph.typing import Agent, Link


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
