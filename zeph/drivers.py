import io
import requests
import time


sleep_time = 30


def get_token(url, username, password):
    res = requests.post(
        url + "/profile/token",
        data={
            "username": username,
            "password": password,
        },
    )
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def check_measurement_finished(url, username, password, measurement_uuid):
    try:
        headers = get_token(url, username, password)
        req = requests.get(url + f"/measurements/{measurement_uuid}", headers=headers)
        res = req.json()["state"] == "finished"
    except Exception:
        return False
    return res


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


# --- adaptive driver


def adaptive_driver(
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
    exploitation_only=False,
    dry_run=False,
):
    """
    Zeph driver.
    """

    headers = get_token(url, username, password)

    if not dry_run:
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

    logger.debug("Get agents")
    req = requests.get(url + "/agents/", headers=headers)
    if req.status_code != 200:
        logger.error("Unable to get agents")
        return (None, None, None)

    selected_agents = [
        a for a in req.json()["results"] if tag in a["parameters"]["agent_tags"]
    ]

    logger.debug("Upload agents targets prefixes")
    agents = []

    exploitation_per_agent = {}
    prefixes_per_agent = {}

    for agent in selected_agents:
        probing_rate = agent["parameters"]["max_probing_rate"]

        budget, n_round = compute_budget(probing_rate)
        if budget == 0:
            continue

        if budget is None:
            target_file = "full.csv"
        else:
            exploitation, total = selector.select(
                agent["uuid"], budget=budget, exploitation_only=exploitation_only
            )
            prefixes_list = [
                (str(p), protocol, str(min_ttl), str(max_ttl)) for p in total
            ]
            exploitation_per_agent[agent["uuid"]] = exploitation
            prefixes_per_agent[agent["uuid"]] = total
            target_file = f"zeph__{agent['uuid']}.csv"

            # Upload the prefixes-list
            if not dry_run:
                is_success = upload_prefixes_list(
                    url, target_file, prefixes_list, headers
                )
                if not is_success:
                    logger.error("Impossible to updoad prefixes list file")
                    return (None, None, None)

        # Add the prefixes-list to the agent specific parameters
        agents.append(
            {
                "uuid": agent["uuid"],
                "target_file": target_file,
                "tool_parameters": {
                    "max_round": n_round,
                    "flow_mapper": "RandomFlowMapper",
                    "flow_mapper_kwargs": {"seed": 2021},
                },
            }
        )
        time.sleep(sleep_time)

    if dry_run:
        return (None, exploitation_per_agent, prefixes_per_agent)

    logger.debug("Launch the measurement")
    req = requests.post(
        url + "/measurements/",
        json={
            "tool": tool,
            "agents": agents,
            "tags": ["test"],
        },
        headers=headers,
    )
    if req.status_code != 201:
        logger.error("Unable to launch measurement")
        return (None, None, None)

    uuid = req.json()["uuid"]
    logger.debug(f"Measurement UUID is `{uuid}`")
    logger.debug("End")

    return (uuid, exploitation_per_agent, prefixes_per_agent)


# --- shared driver


def get_agent_budget(url, username, password, tag, compute_budget):
    headers = get_token(url, username, password)
    req = requests.get(url + "/agents/", headers=headers)
    if req.status_code != 200:
        return None, None

    selected_agents = [
        a for a in req.json()["results"] if tag in a["parameters"]["agent_tags"]
    ]

    agent_budget = {}
    agent_round = {}
    for agent in selected_agents:
        probing_rate = agent["parameters"]["max_probing_rate"]

        budget, n_round = compute_budget(probing_rate)
        if budget == 0:
            continue

        agent_budget[agent["uuid"]] = budget
        agent_round[agent["uuid"]] = n_round

    return agent_budget, agent_round


def shared_driver(
    url,
    username,
    password,
    tool,
    protocol,
    min_ttl,
    max_ttl,
    selector,
    agent_budget,
    agent_round,
    logger,
    dry_run=False,
):
    """
    Shared driver.
    """
    headers = get_token(url, username, password)

    if not dry_run:
        logger.debug("Clean targets")
        req = requests.get(url + "/targets/", headers=headers)
        if req.status_code != 200:
            print(req.text)
            logger.error("Unable to get targets list")
            return (None, None, None)
        for target in req.json()["results"]:
            if target["key"].startswith("shared__"):
                req = requests.delete(
                    url + f"/targets/{target['key']}", headers=headers
                )
                if req.status_code != 200:
                    logger.error(f"Impossible to remove target `{target['key']}`")
                    return (None, None, None)

    logger.debug("Get agents")
    req = requests.get(url + "/agents/", headers=headers)
    if req.status_code != 200:
        logger.error("Unable to get agents")
        return (None, None, None)

    logger.debug("Upload agents targets prefixes")
    agents = []
    exploitation_per_agent = {}
    prefixes_per_agent = {}

    for agent_uuid, budget in agent_budget.items():
        if budget is None:
            target_file = "full.csv"
        else:
            exploitation, total = selector.select(agent_uuid)
            prefixes_list = [
                (str(p), protocol, str(min_ttl), str(max_ttl)) for p in total
            ]
            exploitation_per_agent[agent_uuid] = exploitation
            prefixes_per_agent[agent_uuid] = total
            target_file = f"zeph__{agent_uuid}.csv"

            # Upload the prefixes-list
            if not dry_run:
                is_success = upload_prefixes_list(
                    url, target_file, prefixes_list, headers
                )
                if not is_success:
                    logger.error("Impossible to updoad prefixes list file")
                    return (None, None, None)

        # Add the prefixes-list to the agent specific parameters
        agents.append(
            {
                "uuid": agent_uuid,
                "target_file": target_file,
                "tool_parameters": {
                    "max_round": agent_round[agent_uuid],
                    "flow_mapper": "RandomFlowMapper",
                    "flow_mapper_kwargs": {"seed": 2021},
                },
            }
        )
        time.sleep(sleep_time)

    if dry_run:
        return (None, exploitation_per_agent, prefixes_per_agent)

    logger.debug("Launch the measurement")
    req = requests.post(
        url + "/measurements/",
        json={
            "tool": tool,
            "agents": agents,
            "tags": ["test"],
        },
        headers=headers,
    )
    if req.status_code != 201:
        logger.error(req.text)
        logger.error("Unable to launch measurement")
        return (None, None, None)

    uuid = req.json()["uuid"]
    logger.debug(f"Measurement UUID is `{uuid}`")
    logger.debug("End")

    return (uuid, exploitation_per_agent, prefixes_per_agent)
