from ipaddress import ip_network

from zeph.selectors.constrained import (
    ConstrainedEpsilonDFGSelector,
    ConstrainedRandomSelector,
)


def test_constrained_random_selector(agents_budget, bgp_prefixes):
    selector = ConstrainedRandomSelector(agents_budget, bgp_prefixes)

    exploitation, total = selector.select("agent_1")

    assert exploitation == []
    assert len(total) == 1


def test_constrained_random_selector(agents_budget, discoveries, bgp_prefixes):
    selector = ConstrainedEpsilonDFGSelector(
        "clickhouse://localhost:8123", 0.1, agents_budget, bgp_prefixes
    )

    selector.rank_per_agent = selector.compute_rank(discoveries)
    selector.dispatch_per_agent = selector.compute_dispatch()

    exploitation, total = selector.select("agent_1")

    assert exploitation == {ip_network("10.0.0.0/24")}
    assert len(total) == 1
