from zeph.selectors.random import RandomSelector


def test_random_selector(universe):
    selector = RandomSelector(universe)
    _, prefixes = selector.select("agent_uuid", budget=1)
    assert len(prefixes) == 1
