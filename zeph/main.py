"""
Zeph.

Communicate with Iris to perform measurements.
"""
import logging
from pathlib import Path
from typing import Optional

import typer
from iris_client import IrisClient
from pych_client import ClickHouseClient
from tqdm import tqdm

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

app = typer.Typer()


@app.command()
def zeph(
    prefixes_file: Path = typer.Argument(
        ...,
        help="File containing all the /24 or /64 prefixes that can be probed.",
    ),
    previous_uuid: Optional[str] = typer.Argument(
        None,
        help="UUID of the previous measurement cycle",
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
    iris_base_url: str = typer.Option(
        None,
        help="Iris API URL",
        metavar="BASE_URL",
    ),
    iris_username: str = typer.Option(
        None,
        help="Iris API username",
        metavar="USERNAME",
    ),
    iris_password: str = typer.Option(
        None,
        help="Iris API password",
        metavar="PASSWORD",
    ),
) -> None:
    logging.basicConfig(level=logging.INFO)
    universe = set()
    with prefixes_file.open() as f:
        for line in tqdm(f):
            if line.startswith("#"):
                continue
            line = line.strip()
            assert line.endswith("/24") or line.endswith("/64")
            universe.add(line)
    logger.info("file=%s distinct-prefixes=%s", prefixes_file, len(universe))

    with IrisClient(
        base_url=iris_base_url,
        username=iris_username,
        password=iris_password,
    ) as iris:
        params = {}
        if previous_uuid:
            params["measurement_uuid"] = previous_uuid
        credentials = iris.get("/users/me/services", params=params).json()
        with ClickHouseClient(**credentials["clickhouse"]) as clickhouse:
            run_zeph(
                iris=iris,
                clickhouse=clickhouse,
                ranker=ranker_class,
                universe=universe,
                agent_tag=agent_tag,
                measurement_tags=measurement_tags.split(","),
                tool=tool,
                protocol=protocol,
                min_ttl=min_ttl,
                max_ttl=max_ttl,
                exploration_ratio=exploration_ratio,
                previous_uuid=previous_uuid,
                fixed_budget=fixed_budget,
                dry_run=dry_run,
            )


def run_zeph(
    *,
    iris: IrisClient,
    clickhouse: ClickHouseClient,
    ranker: AbstractRanker | str,
    universe: set[Network],
    agent_tag: str,
    measurement_tags: list[str],
    tool: str,
    protocol: str,
    min_ttl: int,
    max_ttl: int,
    exploration_ratio: float,
    previous_uuid: str | None,
    fixed_budget: int | None,
    dry_run: bool,
) -> None:
    if isinstance(ranker, str):
        ranker_ = getattr(rankers, ranker)()
    else:
        ranker_ = ranker
    # Rank the prefixes based on the previous measurement
    ranked_prefixes = {}
    if previous_uuid:
        logger.info("get-previous-agents")
        previous_agents = get_measurement_agents(iris, previous_uuid)
        logger.info("previous-agents=%s", previous_agents)

        logger.info("get-previous-links")
        query = GetUniqueLinksByPrefix(filter_virtual=True)
        links = query.for_all_agents(clickhouse, previous_uuid, previous_agents)

        logger.info("rank-previous-prefixes")
        ranked_prefixes = ranker_(links)

    logger.info("get-current-agents")
    agents = get_agents(iris, agent_tag)
    logger.info("current-agents=%s", list(agents.keys()))

    logger.info("compute-budget")
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
        logger.info("agent=%s budget=%s", agent_uuid, budgets[agent_uuid])

    # Instantiate the selector
    selector = EpsilonSelector(universe, budgets, exploration_ratio, ranked_prefixes)

    # Select and upload the prefixes
    targets = {}
    for agent_uuid in agents:
        logger.info("agent=%s select-prefixes", agent_uuid)
        prefixes = selector.select(agent_uuid)
        if not dry_run:
            logger.info("agent=%s upload-prefixes", agent_uuid)
            targets[agent_uuid] = upload_prefix_list(
                iris, prefixes, protocol, min_ttl, max_ttl
            )
            logger.info("agent=%s key=%s", agent_uuid, targets[agent_uuid])

    # Create the measurement
    if not dry_run:
        logger.info("create-measurement")
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
        logger.info("measurement_uuid=%s", measurement["uuid"])
