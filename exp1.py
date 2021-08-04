import logging
import pickle
import random
import sys
import time
from math import floor
from pathlib import Path

from zeph.drivers import adaptive_driver, check_measurement_finished
from zeph.prefix import create_bgp_radix, create_bgp_prefixes
from zeph.selectors import EpsilonDFGSelector


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
script_formatter = logging.Formatter(
    "%(asctime)s :: SCRIPT :: %(levelname)s :: %(message)s"
)
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(script_formatter)
logger.addHandler(stream_handler)


pilot_dir = Path("./resources/data/measurements/exp1/")

file_handler = logging.FileHandler(pilot_dir / "log.txt")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(script_formatter)
logger.addHandler(file_handler)

url = "https://iris.dioptra.io/api"
username = "admin"
password = sys.argv[1]

tool = "yarrp"
epsilon = 0.1
protocol = "icmp"
min_ttl = 8
max_ttl = 32

database_host = "127.0.0.1"
database_name = "iris"

mrt_file_path = Path("./resources/mrt/rib.20210801.0000.bz2")
excluded_prefixes_path = Path("./resources/data/excluded_prefixes.txt")
bgp_prefixes_path = Path("./resources/data/bgp_prefixes.pickle")

pilot_n_cycles = 10
pilot_global_budget = 11_881_416
pilot_bgp_prefixes_path = Path("./resources/data/bgp_prefixes.pickle")

# pilot_n_cycles = 5
# pilot_global_budget = 10_000
# pilot_bgp_prefixes_path = Path(
#     f"./resources/data/bgp_prefixes_{pilot_global_budget}.pickle"
# )


def pilot_bgp_prefixes(bgp_prefixes, n_prefixes):
    current_n_prefixes = 0
    subset_bgp_prefixes = []

    random.shuffle(bgp_prefixes)

    for bgp_prefix in bgp_prefixes:
        if current_n_prefixes > n_prefixes:
            break

        subset_bgp_prefixes.append(bgp_prefix)
        current_n_prefixes += len(bgp_prefix)

    logger.info(f"Number of /24 prefixes: {current_n_prefixes}")
    return subset_bgp_prefixes


def create_selector(
    previous_measurement_uuid,
    bgp_prefixes=None,
    bgp_awareness=True,
):
    if bgp_prefixes is None:
        logger.debug("Create BGP radix tree")
        authorized_radix = create_bgp_radix(
            mrt_file_path,
            excluded_filepath=excluded_prefixes_path,
        )
        bgp_prefixes = create_bgp_prefixes(authorized_radix)

    selector = EpsilonDFGSelector(
        database_host,
        database_name,
        epsilon=epsilon,
        authorized_prefixes=bgp_prefixes,
        bgp_awareness=bgp_awareness,
    )

    logger.debug("Get discoveries")
    discoveries = selector.compute_discoveries_links(previous_measurement_uuid)

    logger.debug("Compute rank")
    selector.rank_per_agent = selector.compute_rank(discoveries)

    return selector


def adaptive_instance(
    name,
    n_cycles,
    compute_budget,
    bgp_prefixes=None,
    bgp_awareness=True,
    exploitation_only=False,
    previous_measurement_uuid=None,
    dry_run=False,
):
    """Instance of the experience."""
    measurement_uuid = previous_measurement_uuid
    for _ in range(n_cycles):
        selector = create_selector(
            measurement_uuid, bgp_prefixes=bgp_prefixes, bgp_awareness=bgp_awareness
        )
        measurement_uuid, exploitation_per_agent, prefixes_per_agent = adaptive_driver(
            url,
            username,
            password,
            name,
            tool,
            protocol,
            min_ttl,
            max_ttl,
            selector,
            compute_budget,
            logger,
            exploitation_only=exploitation_only,
            dry_run=dry_run,
        )

        recap = {k: len(v) for k, v in prefixes_per_agent.items()}
        logger.info(f"{name} - {measurement_uuid}: {recap}")

        with (pilot_dir / ("exploitation_" + measurement_uuid + ".pickle")).open(
            "wb"
        ) as fd:
            pickle.dump(exploitation_per_agent, fd)
        with (pilot_dir / ("prefixes_" + measurement_uuid + ".pickle")).open(
            "wb"
        ) as fd:
            pickle.dump(prefixes_per_agent, fd)
        yield measurement_uuid


if __name__ == "__main__":
    # with bgp_prefixes_path.open("rb") as fd:
    #     bgp_prefixes = pickle.load(fd)
    # bgp_prefixes = pilot_bgp_prefixes(bgp_prefixes, pilot_global_budget)
    # logger.info(f"Number of BGP prefixes {len(bgp_prefixes)}")
    # with pilot_bgp_prefixes_path.open("wb") as fd:
    #     pickle.dump(bgp_prefixes, fd)

    with pilot_bgp_prefixes_path.open("rb") as fd:
        bgp_prefixes = pickle.load(fd)
    logger.info(f"Number of BGP prefixes {len(bgp_prefixes)}")

    # All Agent is probing the full budget
    exhaustive_uuids = []
    exhaustive = adaptive_instance(
        "edgenet-1",
        pilot_n_cycles,
        lambda x: (pilot_global_budget, 6),
        bgp_prefixes=bgp_prefixes,
        bgp_awareness=False,
        exploitation_only=False,
    )

    # Compressed Zeph
    # exhaustive_zeph_uuids = []
    # exhaustive_zeph = adaptive_instance(
    #     "exhaustive_zeph",
    #     pilot_n_cycles,
    #     lambda x: (pilot_global_budget + 1000, 6),
    #     bgp_prefixes=bgp_prefixes,
    #     exploitation_only=True,
    # )

    # Constrained Zeph (10%)
    constrained_zeph_uuids_10 = []
    constrained_zeph_10 = adaptive_instance(
        "edgenet-2",
        pilot_n_cycles,
        lambda x: (floor(0.10 * pilot_global_budget), 6),
        bgp_prefixes=bgp_prefixes,
        bgp_awareness=False,
        exploitation_only=False,
    )

    # Constrained Zeph (25%)
    constrained_zeph_uuids_25 = []
    constrained_zeph_25 = adaptive_instance(
        "edgenet-3",
        pilot_n_cycles,
        lambda x: (floor(0.25 * pilot_global_budget), 6),
        bgp_prefixes=bgp_prefixes,
        bgp_awareness=False,
        exploitation_only=False,
    )

    # Constrained Zeph (50%)
    constrained_zeph_uuids_50 = []
    constrained_zeph_50 = adaptive_instance(
        "edgenet-4",
        pilot_n_cycles,
        lambda x: (floor(0.50 * pilot_global_budget), 6),
        bgp_prefixes=bgp_prefixes,
        bgp_awareness=False,
        exploitation_only=False,
    )

    # Constrained Zeph (75%)
    constrained_zeph_uuids_75 = []
    constrained_zeph_75 = adaptive_instance(
        "edgenet-5",
        pilot_n_cycles,
        lambda x: (floor(0.75 * pilot_global_budget), 6),
        bgp_prefixes=bgp_prefixes,
        bgp_awareness=False,
        exploitation_only=False,
    )

    for (
        exhaustive_uuid,
        # exhaustive_zeph_uuid,
        contrained_zeph_uuid_10,
        contrained_zeph_uuid_25,
        contrained_zeph_uuid_50,
        contrained_zeph_uuid_75,
    ) in zip(
        exhaustive,
        # exhaustive_zeph,
        constrained_zeph_10,
        constrained_zeph_25,
        constrained_zeph_50,
        constrained_zeph_75,
    ):
        exhaustive_uuids.append(exhaustive_uuid)
        # exhaustive_zeph_uuids.append(exhaustive_zeph_uuid)

        constrained_zeph_uuids_10.append(contrained_zeph_uuid_10)
        constrained_zeph_uuids_25.append(contrained_zeph_uuid_25)
        constrained_zeph_uuids_50.append(contrained_zeph_uuid_50)
        constrained_zeph_uuids_75.append(contrained_zeph_uuid_75)

        while True:
            check_exhaustive = check_measurement_finished(
                url, username, password, exhaustive_uuid
            )
            # check_exhaustive_zeph = check_measurement_finished(
            #     url, username, password, exhaustive_zeph_uuid
            # )

            check_constrained_zeph_10 = check_measurement_finished(
                url, username, password, contrained_zeph_uuid_10
            )
            check_constrained_zeph_25 = check_measurement_finished(
                url, username, password, contrained_zeph_uuid_25
            )
            check_constrained_zeph_50 = check_measurement_finished(
                url, username, password, contrained_zeph_uuid_50
            )
            check_constrained_zeph_75 = check_measurement_finished(
                url, username, password, contrained_zeph_uuid_75
            )

            if (
                check_exhaustive
                # and check_exhaustive_zeph
                and check_constrained_zeph_10
                and check_constrained_zeph_25
                and check_constrained_zeph_50
                and check_constrained_zeph_75
            ):
                break
            time.sleep(10)

    with (pilot_dir / "exhaustive.txt").open("w") as fd:
        for uuid in exhaustive_uuids:
            fd.write(uuid + "\n")
    # with (pilot_dir / "exhaustive_zeph.txt").open("w") as fd:
    #     for uuid in exhaustive_zeph_uuids:
    #         fd.write(uuid + "\n")
    with (pilot_dir / "constrained_zeph_10.txt").open("w") as fd:
        for uuid in constrained_zeph_uuids_10:
            fd.write(uuid + "\n")
    with (pilot_dir / "constrained_zeph_25.txt").open("w") as fd:
        for uuid in constrained_zeph_uuids_25:
            fd.write(uuid + "\n")
    with (pilot_dir / "constrained_zeph_50.txt").open("w") as fd:
        for uuid in constrained_zeph_uuids_50:
            fd.write(uuid + "\n")
    with (pilot_dir / "constrained_zeph_75.txt").open("w") as fd:
        for uuid in constrained_zeph_uuids_75:
            fd.write(uuid + "\n")
