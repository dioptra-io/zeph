from zeph.selectors.random import RandomSelector


def test_random_selector(bgp_prefixes):
    selector = RandomSelector(bgp_prefixes)
    prefixes = selector.select("agent_uuid", budget=1)
    assert len(prefixes) == 1


def test_random_selector_bgp_awareness(bgp_prefixes):
    selector = RandomSelector(bgp_prefixes, bgp_awareness=True)
    prefixes = selector.select("agent_uuid", budget=1)
    assert len(prefixes) == 1
