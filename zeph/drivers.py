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


def get_database_url(url, headers):
    """Get the database URL."""
    req = requests.get(url + "/users/me/services", headers=headers)
    if req.status_code != 200:
        raise ValueError("Unable to get the database URL")
    data = req.json()
    return f"{data['chproxy_url']}&user={data['chproxy_username']}&password={data['chproxy_password']}"


def get_agents(url, agents_tag, headers):
    """Get the agents."""
    req = requests.get(url + "/agents/", headers=headers)
    if req.status_code != 200:
        raise ValueError("Unable to get the token")

    return [a for a in req.json()["results"] if agents_tag in a["parameters"]["tags"]]


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


def clean_targets(iris_url, agents_uuid, headers):
    for agent_uuid in agents_uuid:
        requests.delete(iris_url + f"/targets/{agent_uuid}", headers=headers)


def iris_driver(
    url,
    username,
    password,
    agents_tag,
    tool,
    protocol,
    min_ttl,
    max_ttl,
    selector,
    compute_budget,
    logger,
    measurement_tags=["test"],
    exploitation_only=False,
    cleanup_targets=True,
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

    # Select the agents to use during the measurement based on the agent tags
    logger.debug("Get agents")
    try:
        selected_agents = get_agents(url, agents_tag, headers)
    except ValueError:
        logger.error("Unable to get agents")
        return (None, None, None)

    # Upload the targets list created using the selector
    logger.debug("Create agents targets prefixes")
    agents = []

    exploitation_per_agent = {}
    prefixes_per_agent = {}

    for agent in selected_agents:
        probing_rate = agent["parameters"]["max_probing_rate"]

        budget = compute_budget(probing_rate)
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

        # Add the prefixes-list to the agent parameters
        agents.append(
            {
                "uuid": agent["uuid"],
                "target_file": target_file_name,
                "tool_parameters": {
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
            "tags": measurement_tags,
        },
        headers=headers,
    )
    if req.status_code != 201:
        logger.error("Unable to launch measurement")
        logger.error(req.text)
        return (None, None, None)

    uuid = req.json()["uuid"]
    logger.debug(f"Measurement UUID is `{uuid}`")

    if not dry_run and cleanup_targets:
        clean_targets(url, selected_agents, headers)

    logger.debug("End")
    return (uuid, exploitation_per_agent, prefixes_per_agent)
