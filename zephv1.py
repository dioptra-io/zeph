"""
Zeph (v1) CLI.

Communicate with Iris to perform measurements.
"""


import click
import logging
import io
import requests
import time

from zeph.prefix import create_bgp_radix, create_bgp_prefixes
from zeph.selectors import EpsilonDFGSelector


# API information
API_URL: str = "https://localhost/v0"
API_USER: str = "admin"
API_PASSWORD: str = "admin"

# Default measurement metadata
PROTOCOL: str = "udp"
DESTINATION_PORT: int = 33434
MIN_TTL: int = 2
MAX_TTL: int = 30
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


def upload_prefixes_list(filename, prefixes_list, AUTH):
    """Upload a targets list given the target list path."""
    fd = io.StringIO()
    fd.write("\n".join(prefixes_list))
    fd.write("\n")
    fd.seek(0)
    req = requests.post(
        API_URL + "/targets/?metadata=prefixes-list",
        files={"targets_file": (filename, fd)},
        auth=AUTH,
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
        return 5_000_000, 6
    if probing_rate == 10_000:
        return 400_000, 10
    elif probing_rate == 2_000:
        return 20_000, 10
    else:
        raise ValueError(probing_rate)


@click.command()
@click.option("--url", default=API_URL)
@click.option("--user", default=API_USER)
@click.option("--password", default=API_PASSWORD)
@click.option("--protocol", default=PROTOCOL)
@click.option("--destination-port", default=DESTINATION_PORT)
@click.option("--min-ttl", default=MIN_TTL)
@click.option("--max-ttl", default=MAX_TTL)
@click.option("--previous-measurement-uuid", default=None)
@click.option("--cycles", default=N_CYCLES)
@click.option("--epsilon", default=EPSILON)
def command(
    url,
    user,
    password,
    protocol,
    destination_port,
    min_ttl,
    max_ttl,
    previous_measurement_uuid,
    cycles,
    epsilon,
):
    logger.info("-" * 5)
    logger.info(f"PROTOCOL: {protocol.upper()}")
    logger.info(f"DESTINATION PORT: {destination_port}")
    logger.info(f"MIN TTL: {min_ttl}")
    logger.info(f"MAX TTL: {max_ttl}")
    logger.info(f"PREVIOUS MEASUREMENT UUID: {previous_measurement_uuid}")
    logger.info(f"NUMBER OF CYCLES : {cycles}")
    logger.info(f"EPSILON : {epsilon}")
    logger.info("-" * 5)

    AUTH = requests.auth.HTTPBasicAuth(user, password)

    logger.info("Clean targets")
    req = requests.get(url + "/targets/", auth=AUTH)
    if req.status_code != 200:
        logger.error("Unable to get targets list")
        exit(1)
    for target in req.json()["results"]:
        if target["key"].startswith("zeph__"):
            req = requests.delete(url + f"/targets/{target['key']}", auth=AUTH)
            if req.status_code != 200:
                logger.error(f"Impossible to remove target `{target['key']}`")

    logger.info("Get agents")
    req = requests.get(API_URL + "/agents/", auth=AUTH)
    if req.status_code != 200:
        logger.error("Unable to get agents")
        exit(1)

    logger.info("Create BGP radix tree")
    authorized_radix = create_bgp_radix(
        "resources/mrt/rib.20210124.1000.bz2",
        excluded_filepath="./resources/excluded_prefixes.txt",
    )
    bgp_prefixes = create_bgp_prefixes(authorized_radix)

    logger.info("Compute rank")
    selector = EpsilonDFGSelector(
        DATABASE_HOST,
        DATABASE_NAME,
        epsilon=epsilon,
        measurement_uuid=previous_measurement_uuid,
        authorized_prefixes=bgp_prefixes,
    )

    logger.info("Upload agents targets prefixes")
    agents = []
    prefixes_per_agent = {}

    for agent in req.json()["results"]:
        probing_rate = agent["parameters"]["probing_rate"]

        budget, n_round = compute_budget(probing_rate)
        if budget == 0:
            continue
        if budget is None:
            agents.append({"uuid": agent["uuid"]})
            continue

        prefixes_list = [str(p) for p in selector.select(agent["uuid"], budget=budget)]
        prefixes_per_agent[agent["uuid"]] = prefixes_list
        targets_file_key = f"zeph__{agent['uuid']}.prefixes"

        # Upload the prefixes-list
        is_success = upload_prefixes_list(targets_file_key, prefixes_list, AUTH)
        if not is_success:
            logger.error("Impossible to updoad prefixes list file")
            exit(1)

        # Add the prefixes-list to the agent specific parameters
        agents.append(
            {
                "uuid": agent["uuid"],
                "targets_file_key": targets_file_key,
                "max_round": n_round,
            }
        )
        time.sleep(1)

    logger.info("Launch the measurement")
    req = requests.post(
        API_URL + "/measurements/",
        json={
            "full": True,
            "agents": agents,
            "protocol": protocol,
            "destination_port": destination_port,
            "min_ttl": min_ttl,
            "max_ttl": max_ttl,
        },
        auth=AUTH,
    )
    if req.status_code != 201:
        logger.error("Unable to launch measurement")
        exit(1)

    uuid = req.json()["uuid"]
    logger.info(f"Measurement UUID is `{uuid}`")
    logger.info("End")


if __name__ == "__main__":
    command()
