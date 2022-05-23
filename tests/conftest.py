from ipaddress import ip_network

import pytest
from pych_client import ClickHouseClient


@pytest.fixture
def budgets():
    yield {"agent_1": 1, "agent_2": 1}


@pytest.fixture
def clickhouse():
    with ClickHouseClient() as client:
        yield client


@pytest.fixture
def links():
    yield {
        ("agent_1", ip_network("10.0.0.0/24"), 1): {1, 2, 3},
        ("agent_1", ip_network("10.0.1.0/24"), 1): {3, 4, 5},
        ("agent_2", ip_network("10.0.2.0/24"), 1): {6},
    }


@pytest.fixture
def universe():
    yield [
        ip_network("10.0.0.0/24"),
        ip_network("10.0.1.0/24"),
        ip_network("10.0.2.0/24"),
    ]
