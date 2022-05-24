from ipaddress import ip_network

from zeph.selectors import EpsilonSelector


def test_epsilon_selector_no_ranks(universe):
    selector = EpsilonSelector(universe, {"a": 1, "b": 1}, 0.5, {})
    prefixes_a = selector.select("a")
    prefixes_b = selector.select("b")
    assert len(prefixes_a) == 1
    assert len(prefixes_b) == 1


def test_epsilon_selector_no_ranks_zero_budget(universe):
    selector = EpsilonSelector(universe, {"a": 0, "b": 1}, 0.5, {})
    prefixes_a = selector.select("a")
    prefixes_b = selector.select("b")
    assert len(prefixes_a) == 0
    assert len(prefixes_b) == 1


def test_epsilon_selector_no_ranks_large_budget(universe):
    selector = EpsilonSelector(universe, {"a": 10, "b": 1}, 0.5, {})
    prefixes_a = selector.select("a")
    prefixes_b = selector.select("b")
    assert len(prefixes_a) == 3
    assert len(prefixes_b) == 1


def test_epsilon_selector_with_ranks(universe):
    ranks = {
        "a": [ip_network("192.168.0.0/24"), ip_network("192.168.1.0/24")],
        "b": [ip_network("192.168.1.0/24"), ip_network("192.168.0.0/24")],
    }
    selector = EpsilonSelector(universe, {"a": 2, "b": 4}, 0.5, ranks)
    prefixes_a = selector.select("a")
    prefixes_b = selector.select("b")
    assert len(prefixes_a) == 2
    assert len(prefixes_b) == 4
    # Exploitation budget for a = 1
    assert ranks["a"][0] in prefixes_a
    assert ranks["a"][1] not in prefixes_a
    # Exploitation budget for b = 2
    assert ranks["b"][0] in prefixes_b
    assert ranks["b"][1] in prefixes_b
