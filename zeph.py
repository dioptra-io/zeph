"""
Zeph CLI.

Communicate with Iris to perform measurements.
"""

import logging
import pickle
from math import floor
from pathlib import Path
from typing import List
from uuid import UUID

import typer

from zeph.bgp import create_bgp_prefixes, create_bgp_radix
from zeph.drivers import (
    create_auth_header,
    get_previous_measurement_agents,
    iris_driver,
)
from zeph.selectors.epsilon import EpsilonDFGSelector

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
script_formatter = logging.Formatter(
    "%(asctime)s :: SCRIPT :: %(levelname)s :: %(message)s"
)
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.DEBUG)
stream_handler.setFormatter(script_formatter)
logger.addHandler(stream_handler)


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
    previous_measurement_uuid: UUID,
    previous_agents_uuid: List[UUID],
    bgp_prefixes: List[List[str]],
):
    """Create prefix selector."""
    selector = EpsilonDFGSelector(
        database_url,
        epsilon=epsilon,
        authorized_prefixes=bgp_prefixes,
    )

    logger.debug("Get discoveries")
    discoveries = selector.compute_discoveries_links(
        previous_measurement_uuid, previous_agents_uuid
    )

    logger.debug("Compute rank")
    selector.rank_per_agent = selector.compute_rank(discoveries)

    return selector


def main(
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
    previous_measurement_uuid: UUID = typer.Option(None),
    epsilon: float = typer.Option(0.1),
    dry_run: bool = False,
):

    logger.info("Create BGP prefix list")
    with open(bgp_prefixes_path, "rb") as fd:
        bgp_prefixes = pickle.load(fd)

    # if mrt_file_path is not None:
    #     logger.info("Create BGP radix tree")
    #     authorized_radix = create_bgp_radix(
    #         mrt_file_path,
    #         excluded_filepath=excluded_prefixes_path,
    #     )
    #     bgp_prefixes = create_bgp_prefixes(authorized_radix)
    #     # Save the BGP prefixes for later use if `bgp_prefixes_path` is set
    #     if bgp_prefixes_path is not None:
    #         with open(bgp_prefixes_path, "wb") as fd:
    #             pickle.dump(bgp_prefixes, fd)
    # elif bgp_prefixes_path is not None:
    #     with open(bgp_prefixes_path, "rb") as fd:
    #         bgp_prefixes = pickle.load(fd)
    # else:
    #     raise ValueError("Supply either BGP prefix path or MRT file path")

    # Get previous measurement agents
    logger.info("Get previous measurement agents")
    if previous_measurement_uuid:
        headers = create_auth_header(api_url, api_username, api_password)
        agents_uuid = get_previous_measurement_agents(
            api_url, previous_measurement_uuid, headers
        )

    # Create the selector
    selector = create_selector(
        database_url,
        epsilon,
        previous_measurement_uuid,
        agents_uuid,
        bgp_prefixes,
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
        default_compute_budget,
        logger,
        clean_targets=True,
        exploitation_only=False,
        dry_run=dry_run,
    )


if __name__ == "__main__":
    typer.run(main)
