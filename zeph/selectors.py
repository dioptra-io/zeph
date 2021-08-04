"""Zeph prefix selectors."""

import itertools
import random

from abc import ABC, abstractmethod
from clickhouse_driver import Client
from collections import defaultdict, Counter, OrderedDict
from ipaddress import ip_network

from diamond_miner.queries import AddrType
from zeph.queries import GetNodeDiscoveries, GetLinkDiscoveries


class AbstractSelector(ABC):
    def _sanitize_uuid(self, uuid):
        return uuid.replace("-", "_")

    def _reverse_sanitize_uuid(self, uuid):
        return uuid.replace("_", "-")

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
        if self.authorized_prefixes:
            # In case the budget is superior to the total number of prefixes
            total_prefixes = sum(len(p) for p in self.authorized_prefixes)
            if total_prefixes < budget:
                for prefixes in self.authorized_prefixes:
                    for prefix in prefixes:
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
                if prefix.prefixlen != 24:
                    continue
            else:
                prefix = next(bgp_prefixes_flat)

            preset.add(prefix)
        return list(preset)


class RandomSelector(AbstractSelector):
    def select(self, agent_uuid, budget: int):
        return self._select_random(agent_uuid, budget)


class RandomSharedSelector(AbstractSelector):
    def __init__(self, agent_budget, authorized_prefixes) -> None:
        self.agent_budget = agent_budget
        self.authorized_prefixes = sorted(authorized_prefixes)

        self.rank_per_agent = self.dispatch()

    def dispatch(self):
        agent_prefixes = defaultdict(list)
        agent_it = itertools.cycle(list(self.agent_budget))

        prefixes = list(itertools.chain(*self.authorized_prefixes))
        random.shuffle(prefixes)
        for prefix in prefixes:
            agent = next(agent_it)
            if len(agent_prefixes[agent]) >= self.agent_budget[agent]:
                continue
            agent_prefixes[agent].append(prefix)

        return agent_prefixes

    def select(self, agent_uuid: str):
        return [], self.rank_per_agent[agent_uuid]


class AbstractEpsilonSelector(AbstractSelector):
    def __init__(
        self,
        database_host,
        database_name,
        epsilon,
        authorized_prefixes=None,
        bgp_awareness=True,
    ):
        self.database_host = database_host
        self.database_name = database_name
        self.database_url = f"clickhouse://{database_host}/{database_name}"

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

    def compute_discoveries_nodes(self, measurement_uuid) -> dict:
        """Get the discoveries per agents."""
        if measurement_uuid is None:
            return

        # Get all measurement tables
        tables = Client.from_url(self.database_url).execute_iter(
            f"SHOW TABLES FROM {self.database_name} LIKE "
            f"'results__{self._sanitize_uuid(measurement_uuid)}%'"
        )
        tables = [table[0] for table in tables]
        measurement_ids = ["__".join(table.split("__")[1:]) for table in tables]

        directives = {}
        for measurement_id in measurement_ids:
            agent = self._reverse_sanitize_uuid(measurement_id.split("__")[1])

            for prefix, protocol, discoveries in GetNodeDiscoveries(
                addr_type=AddrType.FixedString
            ).execute_iter(self.database_url, measurement_id):
                directives[(agent, self.ip_to_network(prefix), protocol)] = set(
                    discoveries
                )
        return directives

    def compute_discoveries_links(self, measurement_uuid) -> dict:
        """Get the discoveries per agents."""
        if measurement_uuid is None:
            return

        # Get all measurement tables
        tables = Client.from_url(self.database_url).execute_iter(
            f"SHOW TABLES FROM {self.database_name} LIKE "
            f"'results__{self._sanitize_uuid(measurement_uuid)}%'"
        )
        tables = [table[0] for table in tables]
        measurement_ids = ["__".join(table.split("__")[1:]) for table in tables]

        directives = {}
        for measurement_id in measurement_ids:
            agent = self._reverse_sanitize_uuid(measurement_id.split("__")[1])

            for prefix, protocol, discoveries in GetLinkDiscoveries(
                addr_type=AddrType.FixedString
            ).execute_iter(self.database_url, measurement_id):
                directives[(agent, self.ip_to_network(prefix), protocol)] = set(
                    discoveries
                )
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


class EpsilonSharedDFGSelector(EpsilonDFGSelector):
    def __init__(
        self,
        database_host,
        database_name,
        epsilon,
        agent_budget,
        authorized_prefixes=None,
        bgp_awareness=True,
    ) -> None:
        self.database_host = database_host
        self.database_name = database_name
        self.database_url = f"clickhouse://{database_host}/{database_name}"

        self.epsilon = epsilon

        self.authorized_prefixes = authorized_prefixes
        self.bgp_awareness = bgp_awareness

        self._discoveries = {}
        self.rank_per_agent = {}

        self.agent_budget = agent_budget
        self.dispatch_per_agent = {}

    def compute_dispatch(self):
        # Get the rank stripped for each agent
        rank_stripped_per_agent = {}
        for agent, budget in self.agent_budget.items():
            budget = self.agent_budget[agent]
            if not self.rank_per_agent or not self.rank_per_agent.get(agent):
                rank_stripped_per_agent[agent] = set()
                continue

            rank = self.rank_per_agent.get(agent)
            n_prefixes_exploration = int(self.epsilon * budget)
            n_prefixes_exploitation = budget - n_prefixes_exploration
            rank_stripped_per_agent[agent] = set(rank[:n_prefixes_exploitation])

        prefixes = list(itertools.chain(*self.authorized_prefixes))
        random.shuffle(prefixes)

        unused_prefixes = []
        for prefix in prefixes:
            for agent_rank in rank_stripped_per_agent.values():
                if prefix in agent_rank:
                    break
            else:
                unused_prefixes.append(prefix)

        prefixes_it = iter(unused_prefixes)

        all_prefix_used = False
        prefix = next(prefixes_it)
        n_agents = len(self.agent_budget)
        agent_count = 0
        for agent in itertools.cycle(list(self.agent_budget)):
            if all_prefix_used:
                break
            if len(rank_stripped_per_agent[agent]) >= self.agent_budget[agent]:
                agent_count += 1
                if agent_count >= n_agents:
                    # We exhaust all budget agents
                    all_prefix_used = True
                continue

            rank_stripped_per_agent[agent].add(prefix)
            try:
                prefix = next(prefixes_it)
                agent_count = 0
            except StopIteration:
                all_prefix_used = True

        return rank_stripped_per_agent

    def select(self, agent_uuid: str):
        if not self.rank_per_agent:
            return [], self.dispatch_per_agent[agent_uuid]

        budget = self.agent_budget[agent_uuid]

        # Compute the number of prefixes for exploration [eB] / exploitation [(1-e)B]
        n_prefixes_exploration = int(self.epsilon * budget)
        n_prefixes_exploitation = budget - n_prefixes_exploration

        # Pick the (1-e)B prefix with the best reward
        rank = self.rank_per_agent[agent_uuid]
        prefixes_exploitation = set(rank[:n_prefixes_exploitation])

        # Add random prefixes until the budget is completely burned
        return prefixes_exploitation.copy(), self.dispatch_per_agent[agent_uuid]
