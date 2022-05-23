"""
Zeph.

Communicate with Iris to perform measurements.
"""

import pickle
from pathlib import Path

import typer
from iris_client import IrisClient
from pych_client import ClickHouseClient

from zeph.budget import AbstractBudget, DefaultBudget, FixedBudget
from zeph.drivers import get_previous_measurement_agents, iris_driver
from zeph.logging import logger
from zeph.queries import GetUniqueLinksByPrefix
from zeph.rankers import DFGCoverRanker
from zeph.selectors.epsilon import EpsilonSelector


def zeph(
    bgp_prefixes_path: Path = typer.Option(...),
    agent_tag: str = typer.Option("all"),
    tool: str = typer.Option("diamond-miner"),
    protocol: str = typer.Option("icmp"),
    min_ttl: int = typer.Option(2),
    max_ttl: int = typer.Option(32),
    epsilon: float = typer.Option(0.1),
    previous_measurement_uuid: str | None = typer.Option(None),
    fixed_budget: int | None = typer.Option(None),
    dry_run: bool = False,
) -> None:

    logger.info("Import BGP prefix list")
    with open(bgp_prefixes_path, "rb") as fd:
        bgp_prefixes = pickle.load(fd)

    with IrisClient() as iris, ClickHouseClient() as clickhouse:
        # Instantiate the selector
        selector = EpsilonSelector(clickhouse, bgp_prefixes, epsilon)
        ranker = DFGCoverRanker()

        # Rank the prefixes based on the previous measurement
        if previous_measurement_uuid:
            logger.info("Get previous measurement agents")
            previous_agents = get_previous_measurement_agents(
                iris, previous_measurement_uuid
            )
            query = GetUniqueLinksByPrefix()
            links = query.for_all_agents(
                clickhouse, previous_measurement_uuid, previous_agents
            )
            selector.ranked_prefixes = ranker(links)

        # Instantiate the budget function
        budget: AbstractBudget = DefaultBudget()
        if fixed_budget:
            budget = FixedBudget(fixed_budget)

        # Launch the measurement using Iris
        iris_driver(
            iris,
            agent_tag,
            tool,
            protocol,
            min_ttl,
            max_ttl,
            selector,
            budget,
            logger,
            dry_run=dry_run,
        )
