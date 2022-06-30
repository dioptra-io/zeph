from zeph.selectors import ConstrainedRandomSelector


def test_constrained_random_selector(universe):
    selector = ConstrainedRandomSelector(universe, {"a": 1, "b": 1})
    prefixes_a = selector.select("a")
    prefixes_b = selector.select("b")
    assert len(prefixes_a) == 1
    assert len(prefixes_b) == 1
    assert len(prefixes_a & prefixes_b) == 0


def test_constrained_random_selector_zero_budget(universe):
    selector = ConstrainedRandomSelector(universe, {"a": 0, "b": 1})
    prefixes_a = selector.select("a")
    prefixes_b = selector.select("b")
    assert len(prefixes_a) == 0
    assert len(prefixes_b) == 1
    assert len(prefixes_a & prefixes_b) == 0


def test_constrained_random_selector_large_budget(universe):
    selector = ConstrainedRandomSelector(universe, {"a": 10, "b": 1})
    prefixes_a = selector.select("a")
    prefixes_b = selector.select("b")
    assert len(prefixes_a) == 2
    assert len(prefixes_b) == 1
    assert len(prefixes_a & prefixes_b) == 0
