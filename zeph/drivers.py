"""API drivers."""
from io import StringIO
from logging import Logger

from iris_client import IrisClient

from zeph.budget import AbstractBudget
from zeph.selectors.abstract import AbstractSelector


def clean_targets(client: IrisClient, keys: list[str]) -> None:
    for key in keys:
        res = client.delete(f"/targets/{key}")
        res.raise_for_status()


def create_measurement(
    client: IrisClient, tool: str, agents: list[dict], tags: list[str]
) -> dict:
    res = client.post(
        "/measurements", json={"tool": tool, "agents": agents, "tags": tags}
    )
    return dict(res.json())  # make mypy happy...


def get_agents(client: IrisClient, tag: str) -> list[dict]:
    return client.all("/agents", params=dict(tag=tag))


def get_previous_measurement_agents(
    client: IrisClient, measurement_uuid: str
) -> list[str]:
    measurement = client.get(f"/measurements/{measurement_uuid}").json()
    return [agent["agent_uuid"] for agent in measurement]


def upload_prefix_list(
    client: IrisClient, key: str, prefixes: list[tuple[str, str, str, str, str]]
) -> None:
    file = StringIO("\n".join(",".join(prefix) for prefix in prefixes))
    res = client.post("/targets", files={"target_file": (key, file)})
    res.raise_for_status()


def iris_driver(
    client: IrisClient,
    agents_tag: str,
    tool: str,
    protocol: str,
    min_ttl: int,
    max_ttl: int,
    selector: AbstractSelector,
    compute_budget: AbstractBudget,
    logger: Logger,
    measurement_tags: list[str] = ["test"],
    cleanup_targets: bool = True,
    dry_run: bool = False,
) -> tuple[str | None, dict, dict]:
    """
    Iris driver.

    Perform the full procedure for creating a measurement to the Iris platform.

    * Get the agents
    * Create the target list of each agent based on the selector
    * Upload the target list via the API
    * Launch the measurement
    """

    # Select the agents to use during the measurement based on the agent tags
    logger.debug("Get agents")
    selected_agents = get_agents(client, agents_tag)

    # Upload the targets list created using the selector
    logger.debug("Create agents targets prefixes")
    agents = []

    exploitation_per_agent = {}
    prefixes_per_agent = {}
    target_files = []

    for agent in selected_agents:
        probing_rate = agent["parameters"]["max_probing_rate"]

        budget = compute_budget(probing_rate)
        if budget == 0:
            # Skip this agent because it has no budget
            continue

        # Select the prefixes with the selector
        exploitation, total = selector.select(agent["uuid"], budget=budget)

        # Target row format: prefix,protocol,min_ttl,max_ttl,n_initial_flows
        prefixes = [
            (str(p), protocol, str(min_ttl), str(max_ttl), str(6)) for p in total
        ]
        exploitation_per_agent[agent["uuid"]] = exploitation
        prefixes_per_agent[agent["uuid"]] = total
        target_file = f"zeph__{agent['uuid']}.csv"

        # Upload the prefixes-list
        if not dry_run:
            upload_prefix_list(client, target_file, prefixes)
            target_files.append(target_file)

        # Add the prefixes-list to the agent parameters
        agents.append(
            {
                "uuid": agent["uuid"],
                "target_file": target_file,
                "tool_parameters": {
                    "flow_mapper": "RandomFlowMapper",
                    "flow_mapper_kwargs": {"seed": 2021},
                },
            }
        )

    if dry_run:
        return None, exploitation_per_agent, prefixes_per_agent

    # Launch the measurement
    logger.debug("Launch the measurement")
    measurement = create_measurement(client, tool, agents, measurement_tags)
    logger.debug(f"Measurement UUID is `{measurement['uuid']}`")

    if not dry_run and cleanup_targets:
        clean_targets(client, target_files)

    logger.debug("End")
    return measurement["uuid"], exploitation_per_agent, prefixes_per_agent
