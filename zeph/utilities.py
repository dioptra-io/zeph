from ipaddress import IPv4Network, IPv6Address, IPv6Network

from diamond_miner.typing import IPNetwork


def addr_to_network(
    addr: IPv6Address, v4_length: int = 24, v6_length: int = 64
) -> IPNetwork:
    if addr_v4 := addr.ipv4_mapped:
        return IPv4Network(f"{addr_v4}/{v4_length}")
    return IPv6Network(f"{addr}/{v6_length}")


def measurement_id(measurement_uuid: str, agent_uuid: str) -> str:
    return f"{measurement_uuid.replace('-', '_')}__{agent_uuid.replace('-', '_')}"
