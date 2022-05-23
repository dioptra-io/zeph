from zeph.selectors.constrained import ConstrainedRandomSelector


def test_constrained_random_selector(universe, budgets):
    selector = ConstrainedRandomSelector(universe, budgets)
    exploitation, total = selector.select("agent_1", 0)
    assert exploitation == set()
    assert len(total) == 1
