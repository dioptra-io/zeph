"""
Zeph.

Communicate with Iris to perform measurements.
"""

import pickle
from math import floor
from pathlib import Path
from typing import List, Optional
from uuid import UUID

import typer

from zeph.drivers import (
    create_auth_header,
    get_previous_measurement_agents,
    iris_driver,
)
from zeph.logging import logger
from zeph.selectors.epsilon import EpsilonDFGSelector


def default_compute_budget(probing_rate: int):
    """
    Compute the budget (number of prefixes to send per agent).
    Based on the probing rate and the approximate duration of the measurement.
    ---
    6 hours at 100_000 kpps -> 200_000 prefixes (from the paper)
    """
    return floor(probing_rate * 2), 10


def create_selector(
    database_url: str,
    epsilon: float,
    bgp_prefixes: List[List[str]],
    previous_measurement_uuid: Optional[UUID] = None,
    previous_agents_uuid: Optional[List[UUID]] = None,
    bgp_awareness: bool = True,
):
    """Create prefix selector."""
    selector = EpsilonDFGSelector(
        database_url,
        epsilon=epsilon,
        authorized_prefixes=bgp_prefixes,
        bgp_awareness=bgp_awareness,
    )

    logger.debug("Get discoveries")
    discoveries = selector.compute_discoveries_links(
        previous_measurement_uuid, previous_agents_uuid
    )

    logger.debug("Compute rank")
    selector.rank_per_agent = selector.compute_rank(discoveries)

    return selector


def zeph(
    api_url: str = typer.Option("https://api.iris.dioptra.io"),
    api_username: str = typer.Option(...),
    api_password: str = typer.Option(...),
    database_url: str = typer.Option("http://localhost:8123?database=iris"),
    bgp_prefixes_path: Path = typer.Option(...),
    agent_tag: str = typer.Option("all"),
    tool: str = typer.Option("diamond-miner"),
    protocol: str = typer.Option("icmp"),
    min_ttl: int = typer.Option(2),
    max_ttl: int = typer.Option(32),
    epsilon: float = typer.Option(0.1),
    previous_measurement_uuid: Optional[UUID] = typer.Option(None),
    bgp_awareness: bool = True,
    fixed_budget: Optional[int] = typer.Option(None),
    dry_run: bool = False,
):

    logger.info("Import BGP prefix list")
    with open(bgp_prefixes_path, "rb") as fd:
        bgp_prefixes = pickle.load(fd)

    # Get previous measurement agents
    agents_uuid = None
    if previous_measurement_uuid:
        logger.info("Get previous measurement agents")
        headers = create_auth_header(api_url, api_username, api_password)
        agents_uuid = get_previous_measurement_agents(
            api_url, previous_measurement_uuid, headers
        )

    # Create the selector
    selector = create_selector(
        database_url,
        epsilon,
        bgp_prefixes,
        previous_measurement_uuid,
        agents_uuid,
        bgp_awareness,
    )

    # Launch the measurement using Iris
    iris_driver(
        api_url,
        api_username,
        api_password,
        agent_tag,
        tool,
        protocol,
        min_ttl,
        max_ttl,
        selector,
        default_compute_budget if not fixed_budget else lambda _: (fixed_budget, 10),
        logger,
        exploitation_only=False,
        dry_run=dry_run,
    )
