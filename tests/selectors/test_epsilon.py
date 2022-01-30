from ipaddress import ip_network

from zeph.selectors.epsilon import EpsilonDFGSelector


def test_epsilon_dfg_selector_first_cycle(bgp_prefixes):
    selector = EpsilonDFGSelector("clickhouse://localhost:8123", 0.1, bgp_prefixes)

    exploitation, total = selector.select("agent_1", budget=1)

    assert exploitation == []
    assert len(total) == 1


def test_epsilon_dfg_selector_with_with_discoveries(bgp_prefixes, discoveries):
    selector = EpsilonDFGSelector("clickhouse://localhost:8123", 0.1, bgp_prefixes)

    selector.rank_per_agent = selector.compute_rank(discoveries)
    exploitation, total = selector.select("agent_1", budget=1)

    assert exploitation == {ip_network("10.0.0.0/24")}
    assert len(total) == 1
