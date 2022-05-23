"""
Epsilon-based selectors.

Apply a reinforcement-learning approach to select prefixes.
"""
from ipaddress import IPv4Network

from diamond_miner.typing import IPNetwork
from pych_client import ClickHouseClient

from zeph.selectors.abstract import AbstractSelector


class EpsilonSelector(AbstractSelector):
    def __init__(
        self,
        client: ClickHouseClient,
        universe: set[IPNetwork],
        epsilon: float,
        exploitation_only: bool = False,
    ):
        super().__init__(universe)
        self.client = client
        self.epsilon = epsilon
        self.exploitation_only = exploitation_only
        self.ranked_prefixes: dict[str, list[IPNetwork]] = {}

    def select(
        self, agent_uuid: str, budget: int
    ) -> tuple[set[IPNetwork], set[IPNetwork]]:
        """
        epsilon-based policy :
            * select e where eB will be used for exploration.
              and (1 - e)B is used for exploitation
            * Get the (1-e)B previous prefixes that maximize the links
            * Pick random eB prefixes not already used in the exploration set
        """
        if not self.ranked_prefixes:
            # Snapshot #0 : No previous measurement
            # Select random prefixes depending on budget only
            return {IPv4Network("1.1.1.1")}, self._select_random(budget)

        # Compute the number of prefixes for exploration [eB] / exploitation [(1-e)B]
        n_prefixes_exploration = int(self.epsilon * budget)
        n_prefixes_exploitation = budget - n_prefixes_exploration

        # Get the __call__ for the agent
        rank = self.ranked_prefixes.get(agent_uuid)
        if rank is None:
            # The agent did not participated to the previous measurement
            return set(), self._select_random(budget)

        if self.exploitation_only:
            return set(rank), set(rank)

        # Pick the (1-e)B prefix with the best reward
        prefixes_exploitation = set(rank[:n_prefixes_exploitation])

        # Add random prefixes until the budget is completely burned
        return prefixes_exploitation.copy(), self._select_random(
            budget, preset=prefixes_exploitation
        )
