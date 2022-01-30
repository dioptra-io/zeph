"""Base for selectors."""

import itertools
import random
from abc import ABC, abstractmethod
from ipaddress import ip_network


class AbstractSelector(ABC):
    def __init__(self, authorized_prefixes, bgp_awareness=False) -> None:
        self.authorized_prefixes = authorized_prefixes
        self.bgp_awareness = bgp_awareness

    def _sanitize_uuid(self, uuid) -> str:
        return str(uuid).replace("-", "_")

    def _reverse_sanitize_uuid(self, uuid) -> str:
        return str(uuid).replace("_", "-")

    @abstractmethod
    def select(*args, **kwargs):
        pass

    def _pick_random(self, agent):
        """Pick a random prefix."""
        a, b, c = (
            random.randint(0, 223),
            random.randint(0, 255),
            random.randint(0, 255),
        )

        return ip_network(f"{a}.{b}.{c}.0/24")

    def _select_random(self, agent, budget, preset=None):
        if preset is None:
            preset = set()

        bgp_prefixes = None
        spread = True

        # In case the budget is superior to the total number of prefixes
        total_prefixes = sum(len(p) for p in self.authorized_prefixes)
        if total_prefixes < budget:
            for prefixes in self.authorized_prefixes:
                for prefix in prefixes:
                    # TODO IPv6 support
                    if prefix.prefixlen != 24:
                        continue
                    preset.add(prefix)
            return preset

        bgp_prefixes = self.authorized_prefixes
        random.shuffle(bgp_prefixes)
        bgp_prefixes_iter = iter(bgp_prefixes)
        bgp_prefixes_flat = iter(list(itertools.chain(*self.authorized_prefixes)))

        while len(preset) < budget:
            if not bgp_prefixes:
                prefix = self._pick_random(agent)
            elif bgp_prefixes and self.bgp_awareness:
                try:
                    next_bgp_prefix = next(bgp_prefixes_iter)
                except StopIteration:
                    # We browsed all the BGP prefixes,
                    # so we go over to pick other /24 prefixes of same supersets
                    bgp_prefixes = self.authorized_prefixes
                    random.shuffle(bgp_prefixes)
                    bgp_prefixes_iter = iter(bgp_prefixes)
                    spread = False
                    continue

                if spread and set.intersection(set(next_bgp_prefix), preset):
                    continue

                prefix = random.choice(next_bgp_prefix)
                # TODO IPv6 support
                if prefix.prefixlen != 24:
                    continue
            else:
                prefix = next(bgp_prefixes_flat)

            preset.add(prefix)
        return list(preset)
