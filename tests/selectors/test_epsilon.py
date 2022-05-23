from ipaddress import ip_network


def test_epsilon_dfg_selector_first_cycle(clickhouse, universe):
    selector = EpsilonDFGSelector(clickhouse, 0.1, universe)

    exploitation, total = selector.select("agent_1", budget=1)

    assert exploitation == []
    assert len(total) == 1


def test_epsilon_reward_selector_with_discoveries(clickhouse, universe, links):
    selector = EpsilonRewardSelector(clickhouse, 0.1, universe)

    selector.ranked_prefixes = selector.compute_rank(links)
    exploitation, total = selector.select("agent_1", budget=1)

    assert exploitation == {ip_network("10.0.0.0/24")}
    assert len(total) == 1


def test_epsilon_naive_selector_with_discoveries(clickhouse, universe, links):
    selector = EpsilonNaiveSelector(clickhouse, 0.1, universe)

    selector.ranked_prefixes = selector.compute_rank(links)
    exploitation, total = selector.select("agent_1", budget=1)

    assert exploitation == {ip_network("10.0.0.0/24")}
    assert len(total) == 1


def test_epsilon_greedy_selector_with_discoveries(clickhouse, universe, links):
    selector = EpsilonGreedySelector(clickhouse, 0.1, universe)

    selector.ranked_prefixes = selector.compute_rank(links)
    exploitation, total = selector.select("agent_1", budget=1)

    assert exploitation == {ip_network("10.0.0.0/24")}
    assert len(total) == 1


def test_epsilon_dfg_selector_with_with_discoveries(clickhouse, universe, links):
    selector = EpsilonDFGSelector(clickhouse, 0.1, universe)

    selector.ranked_prefixes = selector.compute_rank(links)
    exploitation, total = selector.select("agent_1", budget=1)

    assert exploitation == {ip_network("10.0.0.0/24")}
    assert len(total) == 1
