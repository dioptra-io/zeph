import itertools
import pickle
from pathlib import Path

from zeph.prefix import create_bgp_prefixes, create_bgp_radix

mrt_filepath = Path("./resources/mrt/rib.20210801.0000.bz2")
excluded_prefixes_path = Path("./resources/data/excluded_prefixes.txt")

radix = create_bgp_radix(mrt_filepath, excluded_prefixes_path)
prefixes = create_bgp_prefixes(radix)

with Path("./resources/data/bgp_prefixes.pickle").open("wb") as fout:
    pickle.dump(prefixes, fout)

print("* Number of advertized /24", len(set(itertools.chain(*prefixes))))
