"""
Zeph.

Communicate with Iris to perform measurements.
"""

import pickle
from pathlib import Path
from typing import Optional

import typer
from iris_client import IrisClient
from pych_client import ClickHouseClient

from zeph.iris import (
    create_measurement,
    get_agents,
    get_previous_measurement_agents,
    iris_driver,
)
from zeph.logging import logger
from zeph.queries import GetUniqueLinksByPrefix
from zeph.rankers import DFGCoverRanker
from zeph.selectors import EpsilonSelector


def zeph(
    prefixes_file: Path = typer.Argument(
        ..., help="File containing all the /24 or /64 prefixes that can be probed."
    ),
    agent_tag: str = typer.Option("all", metavar="TAG"),
    measurement_tags: str = typer.Option("test,zeph", metavar="TAGS"),
    tool: str = typer.Option("diamond-miner", metavar="TOOL"),
    protocol: str = typer.Option("icmp", metavar="PROTOCOL"),
    min_ttl: int = typer.Option(2, metavar="TTL"),
    max_ttl: int = typer.Option(32, metavar="TTL"),
    exploration_ratio: float = typer.Option(0.1),
    previous_measurement_uuid: Optional[str] = typer.Option(None, metavar="UUID"),
    fixed_budget: Optional[int] = typer.Option(None),
    dry_run: bool = typer.Option(False),
) -> None:

    logger.info("Load prefixes")
    with open(prefixes_file, "rb") as fd:
        universe = pickle.load(fd)

    with IrisClient() as iris, ClickHouseClient() as clickhouse:
        # Rank the prefixes based on the previous measurement
        ranked_prefixes = {}
        if previous_measurement_uuid:
            logger.info("Get previous measurement agents")
            previous_agents = get_previous_measurement_agents(
                iris, previous_measurement_uuid
            )

            logger.info("Get previous links")
            query = GetUniqueLinksByPrefix()
            links = query.for_all_agents(
                clickhouse, previous_measurement_uuid, previous_agents
            )

            logger.info("Rank previous prefixes")
            ranker = DFGCoverRanker()
            ranked_prefixes = ranker(links)

        logger.info("Get current agents")
        agents = get_agents(iris, agent_tag)

        logger.info("Compute agents budget")
        budgets: dict[str, int] = {}
        for agent in agents:
            if fixed_budget:
                budgets[agent["uuid"]] = fixed_budget
            else:
                #  Compute the budget (number of prefixes to send per agent).
                #  Based on the probing rate and the approximate duration of the measurement.
                #  6 hours at 100'000 pps -> 200'000 prefixes (from the paper)
                probing_rate = agent["parameters"]["max_probing_rate"]
                budgets[agent["uuid"]] = probing_rate * 2

        # Instantiate the selector
        selector = EpsilonSelector(universe, budgets, epsilon, ranked_prefixes)

        # Create the measurements
        for agent in agents:
            prefixes = selector.select(agent["uuid"])
            if not dry_run:
                # TODO: Cleanup target lists
                measurement = create_measurement(iris, agent["uuid"], prefixes)

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
