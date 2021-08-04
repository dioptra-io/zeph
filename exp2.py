import logging
import pickle
import random
import sys
import time
from pathlib import Path

from zeph.drivers import (
    adaptive_driver,
    shared_driver,
    check_measurement_finished,
    get_agent_budget,
)
from zeph.prefix import create_bgp_radix, create_bgp_prefixes
from zeph.selectors import (
    EpsilonDFGSelector,
    RandomSharedSelector,
    EpsilonSharedDFGSelector,
)


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
script_formatter = logging.Formatter(
    "%(asctime)s :: SCRIPT :: %(levelname)s :: %(message)s"
)
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(script_formatter)
logger.addHandler(stream_handler)

pilot_dir = Path("./resources/data/measurements/pilot_ya_exp2_10/")

file_handler = logging.FileHandler(pilot_dir / "log.txt")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(script_formatter)
logger.addHandler(file_handler)


url = "https://iris.dioptra.io/api"
username = "admin"
password = sys.argv[1]

tool = "yarrp"
protocol = "icmp"
min_ttl = 13
max_ttl = 32

database_host = "127.0.0.1"
database_name = "iris"

mrt_file_path = Path("./resources/mrt/rib.20210719.1000.bz2")
excluded_prefixes_path = Path("./resources/data/excluded_prefixes.txt")
bgp_prefixes_path = Path("./resources/data/bgp_prefixes.pickle")

pilot_n_cycles = 20
pilot_global_budget = 100_000
n_agents = 2
pilot_bgp_prefixes_path = Path(
    f"./resources/data/bgp_prefixes_{pilot_global_budget}.pickle"
)


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


# --- Adaptive


def create_adaptive_selector(
    epsilon, previous_measurement_uuid, bgp_prefixes=None, bgp_awareness=True
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
    epsilon,
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
        selector = create_adaptive_selector(
            epsilon,
            measurement_uuid,
            bgp_prefixes=bgp_prefixes,
            bgp_awareness=bgp_awareness,
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


# --- Shared


def create_shared_selector(
    name, compute_budget, rl=None, measurement_uuid=None, bgp_prefixes=None
):
    if bgp_prefixes is None:
        logger.debug("Create BGP radix tree")
        authorized_radix = create_bgp_radix(
            mrt_file_path,
            excluded_filepath=excluded_prefixes_path,
        )
        bgp_prefixes = create_bgp_prefixes(authorized_radix)

    agent_budget, agent_round = get_agent_budget(
        url, username, password, name, compute_budget
    )

    if rl:
        selector = EpsilonSharedDFGSelector(
            database_host,
            database_name,
            epsilon=0.1,
            agent_budget=agent_budget,
            authorized_prefixes=bgp_prefixes,
        )
        logger.debug("Get discoveries")
        discoveries = selector.compute_discoveries_links(measurement_uuid)

        logger.debug("Compute rank")
        selector.rank_per_agent = selector.compute_rank(discoveries)

        logger.debug("Compute dispatch")
        selector.dispatch_per_agent = selector.compute_dispatch()
    else:
        selector = RandomSharedSelector(
            agent_budget=agent_budget, authorized_prefixes=bgp_prefixes
        )

    return selector, agent_budget, agent_round


def shared_instance(
    name,
    n_cycles,
    compute_budget,
    rl=False,
    bgp_prefixes=None,
    dry_run=False,
):
    """Instance of the experience."""
    measurement_uuid = None
    for _ in range(n_cycles):
        selector, agent_budget, agent_round = create_shared_selector(
            name,
            compute_budget,
            bgp_prefixes=bgp_prefixes,
            rl=rl,
            measurement_uuid=measurement_uuid,
        )
        measurement_uuid, _, prefixes_per_agent = shared_driver(
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
            dry_run=dry_run,
        )

        recap = {k: len(v) for k, v in prefixes_per_agent.items()}
        logger.info(f"{name} - {measurement_uuid}: {recap}")

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
    # exit()

    with pilot_bgp_prefixes_path.open("rb") as fd:
        bgp_prefixes = pickle.load(fd)
    logger.info(f"Number of BGP prefixes {len(bgp_prefixes)}")

    # Zeph-like
    # adaptive_uuids = []
    # adaptive = adaptive_instance(
    #     "adaptive",
    #     pilot_n_cycles,
    #     0.1,
    #     lambda x: (pilot_global_budget // n_agents, 6),
    #     bgp_prefixes=bgp_prefixes,
    #     bgp_awareness=True,
    #     exploitation_only=False,
    #     # dry_run=True,
    # )

    adaptive_no_bgp_uuids = []
    adaptive_no_bgp = adaptive_instance(
        "adaptive",
        pilot_n_cycles,
        0.1,
        lambda x: (pilot_global_budget // n_agents, 6),
        bgp_prefixes=bgp_prefixes,
        bgp_awareness=False,
        exploitation_only=False,
        # dry_run=True,
    )

    # Exploration only
    # exploration_uuids = []
    # exploration = adaptive_instance(
    #     "exploration",
    #     pilot_n_cycles,
    #     1,
    #     lambda x: (pilot_global_budget // n_agents, 6),
    #     bgp_prefixes=bgp_prefixes,
    #     bgp_awareness=True,
    #     exploitation_only=False,
    #     # dry_run=True,
    # )

    exploration_no_bgp_uuids = []
    exploration_no_bgp = adaptive_instance(
        "exploration",
        pilot_n_cycles,
        1,
        lambda x: (pilot_global_budget // n_agents, 6),
        bgp_prefixes=bgp_prefixes,
        bgp_awareness=False,
        exploitation_only=False,
        # dry_run=True,
    )

    # Ark-like
    shared_uuids = []
    shared = shared_instance(
        "shared",
        pilot_n_cycles,
        lambda x: (pilot_global_budget // n_agents, 6),
        bgp_prefixes=bgp_prefixes,
        # dry_run=True,
    )

    # Ark-like
    adaptive_shared_uuids = []
    adaptive_shared = shared_instance(
        "adaptive_shared",
        pilot_n_cycles,
        lambda x: (pilot_global_budget // n_agents, 6),
        rl=True,
        bgp_prefixes=bgp_prefixes,
        # dry_run=True,
    )

    for (
        adaptive_no_bgp_uuid,
        exploration_no_bgp_uuid,
        shared_uuid,
        adaptive_shared_uuid,
    ) in zip(
        adaptive_no_bgp,
        exploration_no_bgp,
        shared,
        adaptive_shared,
    ):

        # adaptive_uuids.append(adaptive_uuid)
        adaptive_no_bgp_uuids.append(adaptive_no_bgp_uuid)
        # exploration_uuids.append(exploration_uuid)
        exploration_no_bgp_uuids.append(exploration_no_bgp_uuid)
        shared_uuids.append(shared_uuid)
        adaptive_shared_uuids.append(adaptive_shared_uuid)

        while True:
            # check_adaptive = check_measurement_finished(
            #     url, username, password, adaptive_uuid
            # )
            check_adaptive_no_bgp = check_measurement_finished(
                url, username, password, adaptive_no_bgp_uuid
            )

            # check_exploration = check_measurement_finished(
            #     url, username, password, exploration_uuid
            # )
            check_exploration_no_bgp = check_measurement_finished(
                url, username, password, exploration_no_bgp_uuid
            )

            check_shared = check_measurement_finished(
                url, username, password, shared_uuid
            )

            check_adaptive_shared = check_measurement_finished(
                url, username, password, adaptive_shared_uuid
            )

            if (
                # check_adaptive
                check_adaptive_no_bgp
                # and check_exploration
                and check_exploration_no_bgp
                and check_shared
                and check_adaptive_shared
            ):
                break
            time.sleep(1)

    # with (pilot_dir / "adaptive.txt").open("w") as fd:
    #     for uuid in adaptive_uuids:
    #         fd.write(uuid + "\n")
    with (pilot_dir / "adaptive.txt").open("w") as fd:
        for uuid in adaptive_no_bgp_uuids:
            fd.write(uuid + "\n")
    # with (pilot_dir / "exploration.txt").open("w") as fd:
    #     for uuid in exploration_uuids:
    #         fd.write(uuid + "\n")
    with (pilot_dir / "exploration.txt").open("w") as fd:
        for uuid in exploration_no_bgp_uuids:
            fd.write(uuid + "\n")
    with (pilot_dir / "shared.txt").open("w") as fd:
        for uuid in shared_uuids:
            fd.write(uuid + "\n")
    with (pilot_dir / "adaptive_shared.txt").open("w") as fd:
        for uuid in adaptive_shared_uuids:
            fd.write(uuid + "\n")
