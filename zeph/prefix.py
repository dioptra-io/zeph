"""Operations on BGP prefixes."""

import ipaddress
import radix

from mrtparse import Reader, MRT_T, TD_V2_ST, TD_ST
from pathlib import Path


def create_excluded_radix(excluded_filepath: Path):
    tree = radix.Radix()
    with excluded_filepath.open("r") as fd:
        prefixes = fd.readlines()

    for prefix in prefixes:
        tree.add(prefix.strip())
    return tree


def is_excluded(radix, prefix):
    if radix.search_best(str(prefix.network_address)) or radix.search_covered(
        str(prefix)
    ):
        return True
    return False


def is_authorized(radix, prefix):
    f = radix.search_best(str(prefix))
    if f:
        return True
    return False


def is_overlap(radix, preset, prefix):
    bgp_prefixes = [radix.search_best(str(p)) for p in preset]
    f = radix.search_best(str(prefix))
    return f in bgp_prefixes


def create_bgp_radix(mrt_file_path: Path, excluded_filepath: Path = None):
    rtree = radix.Radix()
    if excluded_filepath:
        excluded_tree = create_excluded_radix(excluded_filepath)

    r = Reader(str(mrt_file_path))
    while True:
        try:
            m = r.next()
        except StopIteration:
            break

        if m.err:
            continue
        prefix = "0.0.0.0/0"
        if (
            m.data["type"][0] == MRT_T["TABLE_DUMP_V2"]
            and m.data["subtype"][0] == TD_V2_ST["RIB_IPV4_UNICAST"]
        ):
            prefix = m.data["prefix"] + "/" + str(m.data["prefix_length"])
        elif (
            m.data["type"][0] == MRT_T["TABLE_DUMP"]
            and m.data["subtype"][0] == TD_ST["AFI_IPv4"]
        ):
            prefix = m.data["prefix"] + "/" + str(m.data["prefix_length"])

        if prefix == "0.0.0.0/0":
            continue
        if excluded_filepath:
            f = excluded_tree.search_best(prefix)
            if f:
                continue
        rtree.add(prefix)
    return rtree


def create_bgp_prefixes(radix):
    """Create a list of list of /24 prefixes."""
    bgp_prefixes = list(radix)
    total_prefixes = []

    for bgp_prefix in bgp_prefixes:
        bgp_prefix = bgp_prefix.prefix
        try:
            prefixes = [
                p
                for p in ipaddress.ip_network(bgp_prefix).subnets(new_prefix=24)
                if not p.is_private
            ]
            if prefixes:
                total_prefixes.append(prefixes)
        except ValueError:
            prefix = ipaddress.ip_network(bgp_prefix).supernet(new_prefix=24)
            if prefix.prefixlen != 24:
                continue
            if prefix.is_private:
                continue
            total_prefixes.append([prefix])
    return total_prefixes
