"""
Constrained selectors.

Add the constraint of a prefix being probed by exactly one agent.
It's less effective than letting the agents potentially probe the same prefixes (see paper).
"""

import itertools
import random
from collections import defaultdict

from zeph.selectors.epsilon import EpsilonDFGSelector
from zeph.selectors.random import RandomSelector


class ConstrainedRandomSelector(RandomSelector):
    def __init__(self, agents_budget, authorized_prefixes) -> None:
        self.agents_budget = agents_budget
        self.authorized_prefixes = sorted(authorized_prefixes)

        self.rank_per_agent = self.dispatch()

    def dispatch(self):
        agent_prefixes = defaultdict(list)
        agent_it = itertools.cycle(list(self.agents_budget))

        prefixes = list(itertools.chain(*self.authorized_prefixes))
        random.shuffle(prefixes)
        for prefix in prefixes:
            agent = next(agent_it)
            if len(agent_prefixes[agent]) >= self.agents_budget[agent]:
                continue
            agent_prefixes[agent].append(prefix)

        return agent_prefixes

    def select(self, agent_uuid: str, **kwargs):
        return [], self.rank_per_agent[agent_uuid]


class ConstrainedEpsilonDFGSelector(EpsilonDFGSelector):
    def __init__(
        self,
        database_url: str,
        epsilon: int,
        agents_budget,
        authorized_prefixes,
        bgp_awareness: bool = True,
    ) -> None:
        self.database_url = database_url
        self.epsilon = epsilon

        self.authorized_prefixes = authorized_prefixes
        self.bgp_awareness = bgp_awareness

        self._discoveries = {}
        self.rank_per_agent = {}

        self.agents_budget = agents_budget
        self.dispatch_per_agent = {}

    def compute_dispatch(self):
        # Get the rank stripped for each agent
        rank_stripped_per_agent = {}
        for agent, budget in self.agents_budget.items():
            budget = self.agents_budget[agent]
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
        n_agents = len(self.agents_budget)
        agent_count = 0
        for agent in itertools.cycle(list(self.agents_budget)):
            if all_prefix_used:
                break
            if len(rank_stripped_per_agent[agent]) >= self.agents_budget[agent]:
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

    def select(self, agent_uuid: str, **kwargs):
        if not self.rank_per_agent:
            return [], self.dispatch_per_agent[agent_uuid]

        budget = self.agents_budget[agent_uuid]

        # Compute the number of prefixes for exploration [eB] / exploitation [(1-e)B]
        n_prefixes_exploration = int(self.epsilon * budget)
        n_prefixes_exploitation = budget - n_prefixes_exploration

        # Pick the (1-e)B prefix with the best reward
        rank = self.rank_per_agent[agent_uuid]
        prefixes_exploitation = set(rank[:n_prefixes_exploitation])

        # Add random prefixes until the budget is completely burned
        return prefixes_exploitation.copy(), self.dispatch_per_agent[agent_uuid]
