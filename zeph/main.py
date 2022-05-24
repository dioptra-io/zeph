"""
Zeph.

Communicate with Iris to perform measurements.
"""

from pathlib import Path
from typing import Optional

import typer
from iris_client import IrisClient
from pych_client import ClickHouseClient

from zeph import rankers
from zeph.iris import (
    create_measurement,
    get_agents,
    get_measurement_agents,
    upload_prefix_list,
)
from zeph.logging import logger
from zeph.queries import GetUniqueLinksByPrefix
from zeph.rankers import AbstractRanker
from zeph.selectors import EpsilonSelector
from zeph.typing import Network


def zeph(
    prefixes_file: Path = typer.Argument(
        ...,
        help="File containing all the /24 or /64 prefixes that can be probed.",
    ),
    agent_tag: str = typer.Option(
        "all",
        help="The tag used to select the agents",
        metavar="TAG",
    ),
    measurement_tags: str = typer.Option(
        "test,zeph",
        help="The tags that will be associated to the measurement",
        metavar="TAGS",
    ),
    tool: str = typer.Option(
        "diamond-miner",
        help="The measurement tool",
        metavar="TOOL",
    ),
    protocol: str = typer.Option(
        "icmp",
        help="The probe protocol",
        metavar="PROTOCOL",
    ),
    min_ttl: int = typer.Option(
        2,
        help="The minimum probe TTL",
        metavar="TTL",
    ),
    max_ttl: int = typer.Option(
        32,
        help="The maximum probe TTL",
        metavar="TTL",
    ),
    exploration_ratio: float = typer.Option(
        0.1,
        help="The minimum percentage of the budget allocated to exploration",
    ),
    previous_measurement: Optional[str] = typer.Option(
        None,
        help="UUID of the previous measurement cycle",
        metavar="UUID",
    ),
    fixed_budget: Optional[int] = typer.Option(
        None,
        help="Override the agents budget",
    ),
    ranker_class: str = typer.Option(
        "DFGCoverRanker",
        help="The class to use to rank prefixes",
    ),
    dry_run: bool = typer.Option(
        False,
        help="Do not actually perform the measurement",
    ),
) -> None:
    logger.info("Load prefixes")
    universe = set()
    with prefixes_file.open() as f:
        for line in f:
            if line.startswith("#"):
                continue
            line = line.strip()
            assert line.endswith("/24") or line.endswith("/64")
            universe.add(line)
    logger.info("%s distinct prefixes loaded", len(universe))

    with IrisClient() as iris, ClickHouseClient() as clickhouse:
        ranker = getattr(rankers, ranker_class)()
        run_zeph(
            iris=iris,
            clickhouse=clickhouse,
            ranker=ranker,
            universe=universe,
            agent_tag=agent_tag,
            measurement_tags=measurement_tags.split(","),
            tool=tool,
            protocol=protocol,
            min_ttl=min_ttl,
            max_ttl=max_ttl,
            exploration_ratio=exploration_ratio,
            previous_measurement=previous_measurement,
            fixed_budget=fixed_budget,
            dry_run=dry_run,
        )


def run_zeph(
    *,
    iris: IrisClient,
    clickhouse: ClickHouseClient,
    ranker: AbstractRanker,
    universe: set[Network],
    agent_tag: str,
    measurement_tags: list[str],
    tool: str,
    protocol: str,
    min_ttl: int,
    max_ttl: int,
    exploration_ratio: float,
    previous_measurement: str | None,
    fixed_budget: int | None,
    dry_run: bool,
) -> None:
    # Rank the prefixes based on the previous measurement
    ranked_prefixes = {}
    if previous_measurement:
        logger.info("Get previous agents")
        previous_agents = get_measurement_agents(iris, previous_measurement)
        logger.info("Previous agents: %s", previous_agents)

        logger.info("Get previous links")
        query = GetUniqueLinksByPrefix()
        links = query.for_all_agents(clickhouse, previous_measurement, previous_agents)

        logger.info("Rank previous prefixes")
        ranked_prefixes = ranker(links)

    logger.info("Get current agents")
    agents = get_agents(iris, agent_tag)
    logger.info("Current agents: %s", list(agents.keys()))

    logger.info("Compute agents budget")
    budgets: dict[str, int] = {}
    for agent_uuid, agent in agents.items():
        if fixed_budget:
            budgets[agent_uuid] = fixed_budget
        else:
            # Compute the budget (number of prefixes to send per agent).
            # Based on the probing rate and the approximate duration of the measurement.
            # 6 hours at 100'000 pps -> 200'000 prefixes (from the paper)
            probing_rate = agent["parameters"]["max_probing_rate"]
            budgets[agent_uuid] = probing_rate * 2

    # Instantiate the selector
    selector = EpsilonSelector(universe, budgets, exploration_ratio, ranked_prefixes)

    # Select and upload the prefixes
    targets = {}
    for agent_uuid in agents:
        logger.info("Select prefixes for %s", agent_uuid)
        prefixes = selector.select(agent_uuid)
        if not dry_run:
            logger.info("Upload prefixes for %s", agent_uuid)
            targets[agent_uuid] = upload_prefix_list(
                iris, prefixes, protocol, min_ttl, max_ttl
            )
            logger.info(
                "Uploaded prefixes for %s to %s", agent_uuid, targets[agent_uuid]
            )

    # Create the measurement
    if not dry_run:
        logger.info("Create measurement")
        definition = {
            "tags": measurement_tags,
            "tool": tool,
            "agents": [
                {
                    "uuid": agent_uuid,
                    "target_file": targets[agent_uuid],
                    "tool_parameters": {
                        "flow_mapper": "RandomFlowMapper",
                        "flow_mapper_kwargs": {"seed": 2021},
                    },
                }
                for agent_uuid in agents
            ],
        }
        measurement = create_measurement(iris, definition)
        logger.info("Created measurement %s", measurement["uuid"])
