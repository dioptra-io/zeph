"""
Convert a routeviews RIB file to a list of list of /24 prefixes
that belong to the same announced prefix.

TODO: IPv6 support
"""


import ipaddress
import pickle
from pathlib import Path
from typing import Optional

import radix
import typer
from mrtparse import MRT_T, TD_ST, TD_V2_ST, Reader


def create_excluded_radix(excluded_filepath: Path):
    tree = radix.Radix()
    with excluded_filepath.open("r") as fd:
        prefixes = fd.readlines()

    for prefix in prefixes:
        tree.add(prefix.strip())
    return tree


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
                if not p.is_private and p.prefixlen == 24
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


def main(
    routeviews_filepath: Path,
    bgp_prefixes_path: Optional[Path] = typer.Option(None),
    excluded_prefixes_path: Optional[Path] = typer.Option(None),
):
    authorized_radix = create_bgp_radix(
        routeviews_filepath,
        excluded_filepath=excluded_prefixes_path,
    )
    bgp_prefixes = create_bgp_prefixes(authorized_radix)

    bgp_prefixes_path = bgp_prefixes_path or routeviews_filepath.with_suffix(".pickle")
    with open(bgp_prefixes_path, "wb") as fd:
        pickle.dump(bgp_prefixes, fd)


if __name__ == "__main__":
    typer.run(main)
