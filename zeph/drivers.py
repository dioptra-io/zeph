"""API drivers."""

import io

import requests


def create_auth_header(url, username, password):
    res = requests.post(
        url + "/auth/jwt/login/",
        data={
            "username": username,
            "password": password,
        },
    )
    try:
        return {"Authorization": f"Bearer {res.json()['access_token']}"}
    except KeyError:
        print(res.text)
        raise ValueError("Unable to get the token")


def get_previous_measurement_agents(url, measurement_uuid, headers):
    res = requests.get(url + f"/measurements/{measurement_uuid}", headers=headers)
    agents_uuid = []
    for data in res.json()["agents"]:
        agents_uuid.append(data["agent_uuid"])
    return agents_uuid


def upload_prefixes_list(url, filename, prefixes_list, headers):
    """Upload a targets list given the target list path."""
    fd = io.StringIO()
    for prefix in prefixes_list:
        fd.write(",".join(prefix) + "\n")
    fd.seek(0)

    req = requests.post(
        url + "/targets/",
        files={"target_file": (filename, fd)},
        headers=headers,
    )
    fd.close()
    if req.status_code == 201:
        return True
    else:
        print(req.text)
    return False


def iris_driver(
    url,
    username,
    password,
    tag,
    tool,
    protocol,
    min_ttl,
    max_ttl,
    selector,
    compute_budget,
    logger,
    tags=["test"],
    clean_targets=True,
    exploitation_only=False,
    dry_run=False,
):
    """
    Iris driver.

    Perform the full procedure for creating a measurement to the Iris platform.

    * Get the agents
    * Create the target list of each agent based on the selector
    * Upload the target list via the API
    * Launch the measurement
    """

    headers = create_auth_header(url, username, password)

    # Clean the targets of previous measurements
    if not dry_run and clean_targets:
        logger.debug("Clean targets")
        req = requests.get(url + "/targets/", headers=headers)
        if req.status_code != 200:
            logger.error("Unable to get targets list")
            return (None, None, None)
        for target in req.json()["results"]:
            if target["key"].startswith("zeph__"):
                req = requests.delete(
                    url + f"/targets/{target['key']}", headers=headers
                )
                if req.status_code != 200:
                    logger.error(f"Impossible to remove target `{target['key']}`")

    # Select the agents to use during the measurement based on the agent tags
    logger.debug("Get agents")
    req = requests.get(url + "/agents/", headers=headers)
    if req.status_code != 200:
        logger.error("Unable to get agents")
        return (None, None, None)

    selected_agents = [
        a for a in req.json()["results"] if tag in a["parameters"]["agent_tags"]
    ]

    # Upload the targets list created using the selector
    logger.debug("Create agents targets prefixes")
    agents = []

    exploitation_per_agent = {}
    prefixes_per_agent = {}

    for agent in selected_agents:
        probing_rate = agent["parameters"]["max_probing_rate"]

        budget, n_round = compute_budget(probing_rate)
        if budget == 0:
            # Skip this agent because it has no budget
            continue

        # Select the prefixes with the selector
        exploitation, total = selector.select(
            agent["uuid"], budget=budget, exploitation_only=exploitation_only
        )

        # Target row format: prefix,protocol,min_ttl,max_ttl,n_initial_flows
        prefixes_list = [
            (str(p), protocol, str(min_ttl), str(max_ttl), str(6)) for p in total
        ]
        exploitation_per_agent[agent["uuid"]] = exploitation
        prefixes_per_agent[agent["uuid"]] = total
        target_file_name = f"zeph__{agent['uuid']}.csv"

        # Upload the prefixes-list
        if not dry_run:
            is_success = upload_prefixes_list(
                url, target_file_name, prefixes_list, headers
            )
            if not is_success:
                logger.error("Impossible to updoad prefixes list file")
                return (None, None, None)

        # Add the prefixes-list to the agent  parameters
        agents.append(
            {
                "uuid": agent["uuid"],
                "target_file": target_file_name,
                "tool_parameters": {
                    "max_round": n_round,
                    "flow_mapper": "RandomFlowMapper",
                    "flow_mapper_kwargs": {"seed": 2021},
                },
            }
        )

    if dry_run:
        return (None, exploitation_per_agent, prefixes_per_agent)

    # Launch the measurement
    logger.debug("Launch the measurement")
    req = requests.post(
        url + "/measurements/",
        json={
            "tool": tool,
            "agents": agents,
            "tags": tags,
        },
        headers=headers,
    )
    if req.status_code != 201:
        logger.error("Unable to launch measurement")
        logger.error(req.text)
        return (None, None, None)

    uuid = req.json()["uuid"]
    logger.debug(f"Measurement UUID is `{uuid}`")
    logger.debug("End")

    return (uuid, exploitation_per_agent, prefixes_per_agent)
