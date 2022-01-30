from ipaddress import ip_network

import pytest


@pytest.fixture
def bgp_prefixes():
    """Simulate the output of `create_bgp_prefixes` of `zeph-bgp-convert` script."""
    yield [
        [ip_network("10.0.0.0/24"), ip_network("10.0.1.0/24")],
        [ip_network("10.0.2.0/24")],
    ]


@pytest.fixture
def discoveries():
    yield {
        ("agent_1", ip_network("10.0.0.0/24"), 1): {1, 2, 3},
        ("agent_1", ip_network("10.0.1.0/24"), 1): {3, 4, 5},
        ("agent_2", ip_network("10.0.2.0/24"), 1): {6},
    }
