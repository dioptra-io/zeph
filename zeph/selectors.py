"""Zeph prefix selectors."""

import ipaddress
import random

from abc import ABC, abstractmethod
from clickhouse_driver import Client
from collections import defaultdict, Counter, OrderedDict


class AbstractSelector(ABC):
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

        return ipaddress.ip_network(f"{a}.{b}.{c}.0/24")

    def _select_random(self, agent, budget, preset=None):
        if preset is None:
            preset = set()

        bgp_prefixes = None
        spread = True
        if self.authorized_prefixes:
            bgp_prefixes = self.authorized_prefixes
            random.shuffle(bgp_prefixes)
            bgp_prefixes = iter(bgp_prefixes)

        while len(preset) < budget:
            if not bgp_prefixes:
                prefix = self._pick_random(agent)
            else:
                try:
                    next_bgp_prefix = next(bgp_prefixes)
                except StopIteration:
                    # We browsed all the BGP prefixes,
                    # so we go over to pick other /24 prefixes of same supersets
                    bgp_prefixes = self.authorized_prefixes
                    random.shuffle(bgp_prefixes)
                    bgp_prefixes = iter(bgp_prefixes)
                    spread = False
                    continue

                if spread and set.intersection(set(next_bgp_prefix), preset):
                    continue

                prefix = random.choice(next_bgp_prefix)
                if prefix.prefixlen != 24:
                    continue

            preset.add(prefix)
        return list(preset)


class RandomSelector(AbstractSelector):
    def select(self, agent_uuid, budget: int):
        return self._select_random(agent_uuid, budget)


class AbstractEpsilonSelector(AbstractSelector):
    def __init__(
        self,
        database_host,
        database_name,
        epsilon,
        measurement_uuid=None,
        authorized_prefixes=None,
    ):
        self.client = Client(database_host)
        self.database_name = database_name

        self.epsilon = epsilon
        self.measurement_uuid = measurement_uuid

        self.authorized_prefixes = authorized_prefixes

        self.rank_per_agent = self._rank(self._discoveries(measurement_uuid))

    def _sanitize_uuid(self, uuid):
        return uuid.replace("-", "_")

    def _reverse_sanitize_uuid(self, uuid):
        return uuid.replace("_", "-")

    def _discoveries(self, measurement_uuid):
        """Get the discoveries per agents."""
        if measurement_uuid is None:
            return

        print("* Get discoveries")

        # Get all measurement tables
        tables = self.client.execute_iter(
            f"SHOW TABLES FROM {self.database_name} LIKE "
            f"'results__{self._sanitize_uuid(measurement_uuid)}%'"
        )
        tables = [table[0] for table in tables]
        ipv4_split = 16

        subsets = {}
        for table in tables:
            print(f"** {table}")
            agent = self._reverse_sanitize_uuid(table.split("__")[2])

            discoveries = {}
            for split in range(0, ipv4_split):
                lower_bound = int(split * ((2 ** 32 - 1) / ipv4_split))
                upper_bound = int((split + 1) * ((2 ** 32 - 1) / ipv4_split))

                # Get links and singular nodes
                discoveries_per_split = self.client.execute_iter(
                    "WITH "
                    "groupUniqArray((dst_ip, src_port, dst_port, reply_ip, ttl, round)) as replies_s, "  # noqa
                    "arraySort(x->(x.1, x.2, x.3, x.5), replies_s) as sorted_replies_s, "  # noqa
                    "arrayPopFront(sorted_replies_s) as replies_d, "
                    "arrayConcat(replies_d, [(0,0,0,0,0,0)]) as replies_d_sized, "
                    "arrayZip(sorted_replies_s, replies_d_sized) as potential_links, "
                    "arrayFilter(x->x.1.5 + 1 == x.2.5, potential_links) as links, "
                    "arrayDistinct(arrayMap(x->((x.1.4, x.1.5), (x.2.4, x.2.5)), links)) as links_no_round, "  # noqa
                    "arrayDistinct(arrayMap(x-> (x.1.1,x.2.1), links_no_round)) as links_no_ttl, "  # noqa
                    "arrayDistinct(arrayMap(x->x.4, replies_s)) as nodes, "
                    "arrayDistinct(flatten(arrayMap(x-> [x.1, x.2], links_no_ttl))) AS nodes_in_links, "  # noqa
                    "arrayFilter(x -> has(nodes_in_links, x) = 0, nodes) AS standalone_nodes, "  # noqa
                    "arrayConcat(links_no_ttl, arrayMap(x -> (NULL, x), standalone_nodes)) AS discoveries "  # noqa
                    "SELECT dst_prefix, discoveries "
                    f"FROM {self.database_name}.{table} "
                    "WHERE reply_ip != dst_ip AND type = 11 "
                    f"AND dst_prefix > {lower_bound} AND dst_prefix <= {upper_bound} "
                    "GROUP BY (src_ip, dst_prefix)",
                    settings={
                        "max_block_size": 100000,
                        "connect_timeout": 1000,
                        "send_timeout": 6000,
                        "receive_timeout": 100000,
                        "read_backoff_min_latency_ms": 100000,
                    },
                )
                for prefix, discoveries in discoveries_per_split:
                    subsets[(agent, prefix)] = set(discoveries)
        return subsets

    def select(self, agent_uuid, budget: int):
        """
        epsilon-based policy :
            * select e where eB will be used for exploration.
              and (1 - e)B is used for exploitation
            * Get the (1-e)B previous prefixes that maximize the discoveries
            * Pick random eB prefixes not already used in the exploration set
        """
        if self.rank_per_agent is None:
            # Snapshot #0 : No previous measurement
            # Select random prefixes depending on budget only
            return self._select_random(agent_uuid, budget)

        # Compute the number of prefixes for exploration [eB] / exploitation [(1-e)B]
        n_prefixes_exploration = int(self.epsilon * budget)
        n_prefixes_exploitation = budget - n_prefixes_exploration

        # Get the rank for the agent
        rank = self.rank_per_agent.get(agent_uuid)
        if rank is None:
            # The agent did not participated to the previous measurement
            return self._select_random(agent_uuid, budget)

        # Pick the (1-e)B prefix with the best reward
        prefixes_exploitation = set(rank[:n_prefixes_exploitation])
        prefixes_exploitation = set(
            [
                ipaddress.ip_network(str(ipaddress.ip_address(p)) + "/24")
                for p in prefixes_exploitation
            ]
        )

        # Add random prefixes until the budget is completely burned
        return self._select_random(agent_uuid, budget, preset=prefixes_exploitation)


class EpsilonRewardSelector(AbstractEpsilonSelector):
    def _rank(self, subsets):
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
    def _rank(self, subsets):
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
    def _rank(self, subsets):
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
    def _rank(self, subsets, p=1.05):
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

        print(len(covered))
        return rank_per_agent
