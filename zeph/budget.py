from abc import ABC, abstractmethod
from math import floor


class AbstractBudget(ABC):
    @abstractmethod
    def __call__(self, probing_rate: int) -> int:
        ...


class DefaultBudget(AbstractBudget):
    def __call__(self, probing_rate: int) -> int:
        """
        Compute the budget (number of prefixes to send per agent).
        Based on the probing rate and the approximate duration of the measurement.
        ---
        6 hours at 100_000 kpps -> 200_000 prefixes (from the paper)
        """
        return floor(probing_rate * 2)


class FixedBudget(AbstractBudget):
    def __init__(self, budget: int):
        self.budget = budget

    def __call__(self, probing_rate: int) -> int:
        return self.budget
