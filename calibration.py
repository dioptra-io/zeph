import pickle
from pathlib import Path
from zeph.selectors import EpsilonDFGSelector

database_host = "127.0.0.1"
database_name = "iris"

epsilon = 0.1

# pilot_global_budget = 100_000
# pilot_dir = Path("./resources/data/measurements/pilot_ya_exp1_10/")
# pilot_bgp_prefixes_path = Path(
#     f"./resources/data/bgp_prefixes_{pilot_global_budget}.pickle"
# )

# with pilot_bgp_prefixes_path.open("rb") as fd:
#     bgp_prefixes = pickle.load(fd)

selector = EpsilonDFGSelector(
    database_host,
    database_name,
    epsilon=epsilon,
    authorized_prefixes=None,
    bgp_awareness=False,
)

# with (pilot_dir / "exhaustive.txt").open("r") as fd:
#     exhaustive_uuids = fd.readlines()
# exhaustive_uuid = exhaustive_uuids[0].strip()


exhaustive_uuid = "de9031d9-d9f3-4280-94c9-7ab4cc1a52c3"
discoveries = selector.compute_discoveries_links(exhaustive_uuid)
rank_per_agent = selector.compute_rank(discoveries)

print([len(rank) for rank in rank_per_agent.values()])
