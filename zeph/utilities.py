from ipaddress import IPv4Network, IPv6Address, IPv6Network

from diamond_miner.typing import IPNetwork


def measurement_id(measurement_uuid: str, agent_uuid: str) -> str:
    """
    Return the measurement identifier used by Iris.
    >>> measurement_id("measurement-1", "agent-1")
    'measurement_1__agent_1'
    """
    return f"{measurement_uuid.replace('-', '_')}__{agent_uuid.replace('-', '_')}"


def parse_network(
    addr: str, prefix_len_v4: int = 24, prefix_len_v6: int = 64
) -> IPNetwork:
    """
    Convert an IPv6 address (as stored in the database) to a network object.
    If `addr` is an IPv4-mapped IPv6 address (starting with `::ffff:`) this
    will return an IPv4 network; otherwise it will return an IPv6 network.
    >>> parse_network("::ffff:192.0.2.0")
    IPv4Network('192.0.2.0/24')
    >>> parse_network("2001:db8::")
    IPv6Network('2001:db8::/64')
    """
    addr_v6 = IPv6Address(addr)
    if addr_v4 := addr_v6.ipv4_mapped:
        return IPv4Network(f"{addr_v4}/{prefix_len_v4}")
    return IPv6Network(f"{addr}/{prefix_len_v6}")
