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
    selector = EpsilonSelector(universe, {"a": 2, "b": 2}, 0.5, ranks)
    prefixes_a = selector.select("a")
    prefixes_b = selector.select("b")
    assert len(prefixes_a) == 4
    assert len(prefixes_b) == 2


#
# def test_epsilon_dfg_selector_first_cycle(clickhouse, universe):
#     selector = EpsilonDFGSelector(clickhouse, 0.1, universe)
#
#     exploitation, total = selector.select("agent_1", budget=1)
#
#     assert exploitation == []
#     assert len(total) == 1
#
#
# def test_epsilon_reward_selector_with_discoveries(clickhouse, universe, links):
#     selector = EpsilonRewardSelector(clickhouse, 0.1, universe)
#
#     selector.ranked_prefixes = selector.compute_rank(links)
#     exploitation, total = selector.select("agent_1", budget=1)
#
#     assert exploitation == {ip_network("10.0.0.0/24")}
#     assert len(total) == 1
#
#
# def test_epsilon_naive_selector_with_discoveries(clickhouse, universe, links):
#     selector = EpsilonNaiveSelector(clickhouse, 0.1, universe)
#
#     selector.ranked_prefixes = selector.compute_rank(links)
#     exploitation, total = selector.select("agent_1", budget=1)
#
#     assert exploitation == {ip_network("10.0.0.0/24")}
#     assert len(total) == 1
#
#
# def test_epsilon_greedy_selector_with_discoveries(clickhouse, universe, links):
#     selector = EpsilonGreedySelector(clickhouse, 0.1, universe)
#
#     selector.ranked_prefixes = selector.compute_rank(links)
#     exploitation, total = selector.select("agent_1", budget=1)
#
#     assert exploitation == {ip_network("10.0.0.0/24")}
#     assert len(total) == 1
#
#
# def test_epsilon_dfg_selector_with_with_discoveries(clickhouse, universe, links):
#     selector = EpsilonDFGSelector(clickhouse, 0.1, universe)
#
#     selector.ranked_prefixes = selector.compute_rank(links)
#     exploitation, total = selector.select("agent_1", budget=1)
#
#     assert exploitation == {ip_network("10.0.0.0/24")}
#     assert len(total) == 1
