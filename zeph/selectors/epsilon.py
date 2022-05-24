"""
Epsilon-based selectors.

Apply a reinforcement-learning approach to select prefixes.
"""


from zeph.selectors.abstract import AbstractSelector
from zeph.typing import Network


class EpsilonSelector(AbstractSelector):
    def __init__(
        self,
        universe: set[Network],
        budgets: dict[str, int],
        epsilon: float,
        ranked_prefixes: dict[str, list[Network]],
    ):
        super().__init__(universe, budgets)
        self.epsilon = epsilon
        self.ranked_prefixes = ranked_prefixes

    def select(self, agent_uuid: str) -> set[Network]:
        """
        epsilon-based policy :
            * select e where eB will be used for exploration.
              and (1 - e)B is used for exploitation
            * Get the (1-e)B previous prefixes that maximize the links
            * Pick random eB prefixes not already used in the exploration set
        """
        # Compute the number of prefixes for exploration [eB] / exploitation [(1-e)B]
        n_prefixes_exploitation = int((1 - self.epsilon) * self.budgets[agent_uuid])

        # Pick the (1-e)B prefix with the best reward
        rank = self.ranked_prefixes.get(agent_uuid, [])
        prefixes = set(rank[:n_prefixes_exploitation])

        # Add random prefixes until the budget is completely burned
        return self._select_random(agent_uuid, preset=prefixes)
