from zeph.selectors import RandomSelector


def test_random_selector(universe):
    selector = RandomSelector(universe, {"a": 1, "b": 1})
    prefixes_a = selector.select("a")
    prefixes_b = selector.select("b")
    assert len(prefixes_a) == 1
    assert len(prefixes_b) == 1


def test_random_selector_zero_budget(universe):
    selector = RandomSelector(universe, {"a": 0, "b": 1})
    prefixes_a = selector.select("a")
    prefixes_b = selector.select("b")
    assert len(prefixes_a) == 0
    assert len(prefixes_b) == 1


def test_random_selector_large_budget(universe):
    selector = RandomSelector(universe, {"a": 10, "b": 1})
    prefixes_a = selector.select("a")
    prefixes_b = selector.select("b")
    assert len(prefixes_a) == 3
    assert len(prefixes_b) == 1
