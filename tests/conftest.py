import ipaddress

import pytest


@pytest.fixture
def bgp_prefixes():
    """Simulate the output of `create_bgp_prefixes` of `zeph-bgp-convert` script."""
    yield [
        [ipaddress.ip_network("10.0.0.0/24"), ipaddress.ip_network("10.0.1.0/24")],
        [ipaddress.ip_network("10.0.2.0/24")],
    ]
