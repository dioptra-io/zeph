"""
Zeph (v1) CLI.

Communicate with Iris to perform measurements.
"""

import logging
import typer
import pickle

from pathlib import Path
from uuid import UUID

from zeph.drivers import adaptive_driver
from zeph.prefix import create_bgp_radix, create_bgp_prefixes
from zeph.selectors import EpsilonDFGSelector


# API information
API_URL: str = "https://iris.dioptra.io/api"
API_USERNAME: str = "admin"

# Default measurement metadata
AGENT_TAG: str = "all"
TOOL: str = "diamond-miner"
PROTOCOL: str = "icmp"
MIN_TTL: int = 2
MAX_TTL: int = 32
EPSILON: float = 0.1

# Database information
DATABASE_HOST = "127.0.0.1"
DATABASE_NAME = "iris"


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
    Compute the budget (number of prefixes).
    This budget depends on the probing rate and an approximation of the time in hours.

    100_000 pps -> 10_000_000 prefixes in 35h
    ---
    hour/35 * 100 * probing_rate = n_prefixes
    """
    if probing_rate >= 100_000:
        return None, 6
    if probing_rate == 10_000:
        return 400_000, 10
    elif probing_rate == 2_000:
        return 20_000, 10
    else:
        raise ValueError(probing_rate)


def create_selector(
    database_host: str,
    database_name: str,
    epsilon: float,
    previous_measurement_uuid: UUID,
    bgp_prefixes: Path,
):
    """Create prefix selector."""
    selector = EpsilonDFGSelector(
        database_host,
        database_name,
        epsilon=epsilon,
        authorized_prefixes=bgp_prefixes,
    )

    logger.debug("Get discoveries")
    discoveries = selector.compute_discoveries_links(previous_measurement_uuid)

    logger.debug("Compute rank")
    selector.rank_per_agent = selector.compute_rank(discoveries)

    return selector


def main(
    url: str = typer.Option(API_URL),
    database_host: str = typer.Option(DATABASE_HOST),
    database_name: str = typer.Option(DATABASE_NAME),
    username: str = typer.Option(API_USERNAME),
    password: str = typer.Option(...),
    agent_tag: str = typer.Option(AGENT_TAG),
    tool: str = typer.Option(TOOL),
    protocol: str = typer.Option(PROTOCOL),
    min_ttl: int = typer.Option(MIN_TTL),
    max_ttl: int = typer.Option(MAX_TTL),
    previous_measurement_uuid: UUID = typer.Option(None),
    epsilon: float = typer.Option(EPSILON),
    bgp_prefixes_path: Path = typer.Option(None),
    mrt_file_path: Path = typer.Option(None),
    excluded_prefixes_path: Path = typer.Option(None),
    dry_run: bool = False,
):
    logger.info("Create BGP prefix list")
    if bgp_prefixes_path is not None:
        with open(bgp_prefixes_path, "rb") as fd:
            bgp_prefixes = pickle.load(fd)
    elif mrt_file_path is not None:
        logger.info("Create BGP radix tree")
        authorized_radix = create_bgp_radix(
            mrt_file_path,
            excluded_filepath=excluded_prefixes_path,
        )
        bgp_prefixes = create_bgp_prefixes(authorized_radix)
        with open("./resources/data/bgp_prefixes.txt", "wb") as fd:
            pickle.dump(bgp_prefixes, fd)
    else:
        raise ValueError("Supply either BGP prefix path or MRT file path")

    # Create the selector
    selector = create_selector(
        database_host,
        database_name,
        epsilon,
        previous_measurement_uuid,
        bgp_prefixes=bgp_prefixes,
    )

    # Launch the measurement
    adaptive_driver(
        url,
        username,
        password,
        agent_tag,
        tool,
        protocol,
        min_ttl,
        max_ttl,
        selector,
        default_compute_budget,
        logger,
        exploitation_only=False,
        dry_run=dry_run,
    )


if __name__ == "__main__":
    typer.run(main)
