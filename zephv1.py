"""
Zeph (v1) CLI.

Communicate with Iris to perform measurements.
"""

import click
import logging
import io
import pickle
import requests
import time

from zeph.prefix import create_bgp_radix, create_bgp_prefixes
from zeph.selectors import EpsilonDFGSelector


# API information
API_URL: str = "https://iris.dioptra.io/api"
API_USERNAME: str = "admin"

# Default measurement metadata
PROTOCOL: str = "icmp"
DESTINATION_PORT: int = 33434
MIN_TTL: int = 2
MAX_TTL: int = 32
N_CYCLES: int = 1
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


def get_token(url, username, password):
    res = requests.post(
        url + "/profile/token",
        data={
            "username": username,
            "password": password,
        },
    )
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


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


def compute_budget(probing_rate):
    """
    Compute the budget (number of prefixes).
    This budget depends on the probing rate and an approximation of the time in hours.

    100_000 pps -> 10_000_000 prefixes in 35h
    ---
    hour/35 * 100 * probing_rate = n_prefixes
    """
    if probing_rate >= 100_000:
        return 0, 6
    if probing_rate == 10_000:
        return 400_000, 10
    elif probing_rate == 2_000:
        return 20_000, 10
    else:
        raise ValueError(probing_rate)


@click.command()
@click.option("--url", default=API_URL)
@click.option("--username", default=API_USERNAME)
@click.option("--password", default=None)
@click.option("--protocol", default=PROTOCOL)
@click.option("--destination-port", default=DESTINATION_PORT)
@click.option("--min-ttl", default=MIN_TTL)
@click.option("--max-ttl", default=MAX_TTL)
@click.option("--previous-measurement-uuid", default=None)
@click.option("--epsilon", default=EPSILON)
@click.option("--bgp-prefixes", default=None)
@click.option("--radix", default=None)
@click.option("--excluded-prefixes", default=None)
def command(
    url,
    username,
    password,
    protocol,
    destination_port,
    min_ttl,
    max_ttl,
    previous_measurement_uuid,
    epsilon,
    bgp_prefixes,
    radix,
    excluded_prefixes,
):
    logger.info("-" * 5)
    logger.info(f"PROTOCOL: {protocol.upper()}")
    logger.info(f"DESTINATION PORT: {destination_port}")
    logger.info(f"MIN TTL: {min_ttl}")
    logger.info(f"MAX TTL: {max_ttl}")
    logger.info(f"PREVIOUS MEASUREMENT UUID: {previous_measurement_uuid}")
    logger.info(f"EPSILON : {epsilon}")
    logger.info("-" * 5)

    if password is None:
        logger.error("Please provide a password")
        exit(1)

    headers = get_token(url, username, password)

    logger.info("Clean targets")
    req = requests.get(url + "/targets/", headers=headers)
    if req.status_code != 200:
        print(req.text)
        logger.error("Unable to get targets list")
        exit(1)
    for target in req.json()["results"]:
        if target["key"].startswith("zeph__"):
            req = requests.delete(url + f"/targets/{target['key']}", headers=headers)
            if req.status_code != 200:
                logger.error(f"Impossible to remove target `{target['key']}`")

    logger.info("Get agents")
    req = requests.get(API_URL + "/agents/", headers=headers)
    if req.status_code != 200:
        logger.error("Unable to get agents")
        exit(1)

    # logger.info("Create BGP prefix list")
    # if bgp_prefixes is not None:
    #     with open(bgp_prefixes, "rb") as fd:
    #         bgp_prefixes = pickle.load(fd)
    # elif radix is not None:
    #     logger.info("Create BGP radix tree")
    #     authorized_radix = create_bgp_radix(
    #         radix,
    #         excluded_filepath=excluded_prefixes,
    #     )
    #     bgp_prefixes = create_bgp_prefixes(authorized_radix)

    #     with open("./resources/data/bgp_prefixes.txt", "wb") as fd:
    #         pickle.dump(bgp_prefixes, fd)

    # selector = EpsilonDFGSelector(
    #     DATABASE_HOST,
    #     DATABASE_NAME,
    #     epsilon=epsilon,
    #     authorized_prefixes=bgp_prefixes,
    # )

    # logger.info("Get discoveries")
    # discoveries = selector.compute_discoveries(previous_measurement_uuid)

    # logger.info("Compute rank")
    # selector.rank_per_agent = selector.compute_rank(discoveries)
    # with open("./resources/data/selector.pickle", "wb") as fd:
    #     pickle.dump(selector, fd)

    with open("./resources/data/selector.pickle", "rb") as fd:
        selector = pickle.load(fd)

    logger.info("Upload agents targets prefixes")
    agents = []
    prefixes_per_agent = {}

    for agent in req.json()["results"]:
        probing_rate = agent["parameters"]["max_probing_rate"]

        budget, n_round = compute_budget(probing_rate)
        if budget is None:
            continue

        if budget is None:
            target_file = "full.csv"
        else:
            prefixes_list = [
                (str(p), protocol, str(min_ttl), str(max_ttl))
                for p in selector.select(
                    agent["uuid"], budget=budget, exploitation_only=(not bool(budget))
                )
            ]
            prefixes_per_agent[agent["uuid"]] = prefixes_list
            target_file = f"zeph__{agent['uuid']}.csv"

            # Upload the prefixes-list
            is_success = upload_prefixes_list(url, target_file, prefixes_list, headers)
            if not is_success:
                logger.error("Impossible to updoad prefixes list file")
                exit(1)

        # Add the prefixes-list to the agent specific parameters
        agents.append(
            {
                "uuid": agent["uuid"],
                "target_file": target_file,
                "max_round": n_round,
            }
        )
        time.sleep(1)

    logger.info("Launch the measurement")
    req = requests.post(
        url + "/measurements/",
        json={
            "tool": "diamond-miner",
            "agents": agents,
        },
        headers=headers,
    )
    if req.status_code != 201:
        logger.error("Unable to launch measurement")
        exit(1)

    uuid = req.json()["uuid"]
    logger.info(f"Measurement UUID is `{uuid}`")
    logger.info("End")


if __name__ == "__main__":
    command()
