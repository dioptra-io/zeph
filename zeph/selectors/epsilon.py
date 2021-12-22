"""
Epsilon-based selectors.

Apply a reinforcement-learning approach to select prefixes.
"""

from collections import Counter, OrderedDict, defaultdict
from ipaddress import ip_address, ip_network

from zeph.queries import GetLinkDiscoveries, GetNodeDiscoveries
from zeph.selectors.abstract import AbstractSelector


class AbstractEpsilonSelector(AbstractSelector):
    def __init__(
        self,
        database_url,
        epsilon,
        authorized_prefixes,
        bgp_awareness=True,
    ):
        self.database_url = database_url

        self.epsilon = epsilon

        self.authorized_prefixes = authorized_prefixes
        self.bgp_awareness = bgp_awareness

        self._discoveries = {}
        self.rank_per_agent = {}

    def ip_to_network(self, ip, v4_length=24, v6_length=64) -> str:
        ip_mapped = ip.ipv4_mapped
        if ip_mapped:
            return ip_network(f"{ip_mapped}/{v4_length}")
        return ip_network(f"{ip}/{v6_length}")

    def compute_discoveries_nodes(self, measurement_uuid, agents_uuid) -> dict:
        """Get the discoveries (nodes) per agents."""
        if measurement_uuid is None:
            return

        directives = {}
        for agent_uuid in agents_uuid:
            measurement_id = (
                self._sanitize_uuid(measurement_uuid)
                + "__"
                + self._sanitize_uuid(agent_uuid)
            )
            for data in GetNodeDiscoveries().execute_iter(
                self.database_url, measurement_id
            ):
                directives[
                    (
                        agent_uuid,
                        self.ip_to_network(ip_address(data["probe_dst_prefix"])),
                        data["probe_protocol"],
                    )
                ] = set(data["discoveries"])
        return directives

    def compute_discoveries_links(self, measurement_uuid, agents_uuid) -> dict:
        """Get the discoveries (links) per agents."""
        if measurement_uuid is None:
            return

        directives = {}
        for agent_uuid in agents_uuid:
            measurement_id = (
                self._sanitize_uuid(measurement_uuid)
                + "__"
                + self._sanitize_uuid(agent_uuid)
            )
            for data in GetLinkDiscoveries().execute_iter(
                self.database_url, measurement_id
            ):
                directives[
                    (
                        agent_uuid,
                        self.ip_to_network(ip_address(data["probe_dst_prefix"])),
                        data["probe_protocol"],
                    )
                ] = set([tuple(link) for link in data["discoveries"]])
        return directives

    def select(self, agent_uuid, budget: int, exploitation_only=False):
        """
        epsilon-based policy :
            * select e where eB will be used for exploration.
              and (1 - e)B is used for exploitation
            * Get the (1-e)B previous prefixes that maximize the discoveries
            * Pick random eB prefixes not already used in the exploration set
        """
        if not self.rank_per_agent:
            # Snapshot #0 : No previous measurement
            # Select random prefixes depending on budget only
            return [], self._select_random(agent_uuid, budget)

        # Compute the number of prefixes for exploration [eB] / exploitation [(1-e)B]
        n_prefixes_exploration = int(self.epsilon * budget)
        n_prefixes_exploitation = budget - n_prefixes_exploration

        # Get the rank for the agent
        rank = self.rank_per_agent.get(agent_uuid)
        if rank is None:
            # The agent did not participated to the previous measurement
            return [], self._select_random(agent_uuid, budget)

        if exploitation_only:
            return set(rank), set(rank)

        # Pick the (1-e)B prefix with the best reward
        prefixes_exploitation = set(rank[:n_prefixes_exploitation])

        # Add random prefixes until the budget is completely burned
        return prefixes_exploitation.copy(), self._select_random(
            agent_uuid, budget, preset=prefixes_exploitation
        )


class EpsilonRewardSelector(AbstractEpsilonSelector):
    def compute_rank(self, subsets):
        """Compute the prefixes reward per agent based on the discoveries."""
        if subsets is None:
            return

        # Count the discoveries
        discoveries_counter = Counter()
        for subset, discoveries in subsets.values():
            discoveries_counter.update(discoveries)

        # Compute the reward (#unique_discoveries per prefix per agent)
        rewards_per_agent = defaultdict(dict)
        for subset, discoveries in subsets.items():
            agent, prefix = subset
            rewards_per_agent[agent][prefix] = [
                discovery
                for discovery in discoveries
                if discoveries_counter[discovery] == 1
            ]

        rank_per_agent = dict()
        for source_ip, rewards_per_prefix in rewards_per_agent.items():
            rank = [(k, len(v)) for k, v in rewards_per_prefix.items()]
            rank = sorted(rank, key=lambda x: x[1], reverse=True)
            rank_per_agent[source_ip] = [prefix[0] for prefix in rank]

        return rank_per_agent


class EpsilonNaiveSelector(AbstractEpsilonSelector):
    def compute_rank(self, subsets):
        """Compute the prefixes rank per agent based on the discoveries."""
        if subsets is None:
            return

        total_discoveries = set()
        rank_per_agent = defaultdict(list)

        for subset, discoveries in subsets.items():
            total_discoveries.update(discoveries)

        # Sort the subsets by size in descending order
        subsets = OrderedDict(
            sorted(
                [(k, v) for k, v in subsets.items()],
                key=lambda x: len(x[1]),
                reverse=True,
            )
        )

        covered = set()

        for subset in subsets:
            if covered == total_discoveries:
                break

            if subsets[subset] - covered:
                rank_per_agent[subset[0]].append(subset[1])
                covered.update(subsets[subset])

        return rank_per_agent


class EpsilonGreedySelector(AbstractEpsilonSelector):
    def compute_rank(self, subsets):
        """Compute the prefixes rank per agent based on the discoveries."""
        if subsets is None:
            return

        total_discoveries = set()
        rank_per_agent = defaultdict(list)

        for subset, discoveries in subsets.items():
            total_discoveries.update(discoveries)

        covered = set()

        while covered != total_discoveries and subsets:
            subset = max(subsets, key=lambda subset: len(subsets[subset] - covered))

            rank_per_agent[subset[0]].append(subset[1])
            covered.update(subsets[subset])
            del subsets[subset]

        return rank_per_agent


class EpsilonDFGSelector(AbstractEpsilonSelector):
    def compute_rank(self, subsets, p=1.05):
        """Compute the prefixes rank per agent based on the discoveries."""
        if subsets is None:
            return

        rank_per_agent = defaultdict(list)

        # Populate the subcollections
        subcollections = defaultdict(list)
        for subset in subsets:
            k = 0
            while p ** (k + 1) < len(subsets[subset]):
                k += 1
            subcollections[k].append(subset)
        k_max = max(subcollections.keys())

        covered = set()

        # k = k_max ... 1
        for k in range(k_max, 0, -1):
            for subset in subcollections[k]:
                if len(subsets[subset] - covered) >= p ** k:
                    rank_per_agent[subset[0]].append(subset[1])
                    covered.update(subsets[subset])
                else:
                    subsets[subset] = subsets[subset] - covered
                    k_prime = 0
                    while p ** (k_prime + 1) < len(subsets[subset]):
                        k_prime += 1
                    subcollections[k_prime].append(subset)

        # k = 0
        for subset in subcollections[0]:
            if len(subsets[subset] - covered) == 1:
                rank_per_agent[subset[0]].append(subset[1])
                covered.update(subsets[subset])

        return rank_per_agent
