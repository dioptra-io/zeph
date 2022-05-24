from ipaddress import ip_network

import pytest


@pytest.fixture
def universe():
    yield [
        ip_network("10.0.0.0/24"),
        ip_network("10.0.1.0/24"),
        ip_network("10.0.2.0/24"),
    ]
