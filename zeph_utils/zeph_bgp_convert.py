"""
Convert a RIB file to a list of /24 prefixes.
TODO: IPv6 support.
"""
from ipaddress import IPv4Network, ip_network
from pathlib import Path

import typer
from pyasn.mrtx import parse_mrt_file
from tqdm import tqdm


def main(
    input_file: Path = typer.Argument(...),
    output_file: Path = typer.Argument(...),
    print_progress: bool = False,
    skip_record_on_error: bool = False,
) -> None:
    prefixes = parse_mrt_file(str(input_file), print_progress, skip_record_on_error)
    with output_file.open("w") as f:
        for prefix in tqdm(prefixes, disable=not print_progress):
            net = ip_network(prefix)
            if isinstance(net, IPv4Network):
                if net.prefixlen <= 24:
                    for subnet in net.subnets(new_prefix=24):
                        f.write(f"{subnet}\n")


def run() -> None:
    """
    Run the CLI from a path like `zeph_utils.zeph_bgp_convert:run`.
    Useful for poetry.
    """
    typer.run(main)


if __name__ == "__main__":
    run()
