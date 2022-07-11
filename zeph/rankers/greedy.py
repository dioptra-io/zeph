from collections import defaultdict

from zeph.rankers import AbstractRanker
from zeph.typing import Agent, Link, Network


class GreedyCoverRanker(AbstractRanker):
    def __call__(
        self, links: dict[tuple[Agent, Network], set[Link]]
    ) -> dict[Agent, list[Network]]:
        all_links: set[Link] = set()
        covered: set[Link] = set()
        prefixes: dict[Agent, list[Network]] = defaultdict(list)

        for links_ in links.values():
            all_links.update(links_)

        while covered != all_links and links:
            agent, prefix = max(links, key=lambda k: len(links[k] - covered))
            prefixes[agent].append(prefix)
            covered.update(links[(agent, prefix)])
            links.pop((agent, prefix))

        return prefixes
