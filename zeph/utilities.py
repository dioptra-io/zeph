def measurement_id(measurement_uuid: str, agent_uuid: str) -> str:
    """
    Return the measurement identifier used by Iris.
    >>> measurement_id("measurement-1", "agent-1")
    'measurement_1__agent_1'
    """
    return f"{measurement_uuid.replace('-', '_')}__{agent_uuid.replace('-', '_')}"


def parse_network(addr: str, prefix_len_v4: int = 24, prefix_len_v6: int = 64) -> str:
    """
    Convert an IPv6 address (as stored in the database) to a network string.
    If `addr` is an IPv4-mapped IPv6 address (starting with `::ffff:`) this
    will return an IPv4 network; otherwise it will return an IPv6 network.
    >>> parse_network("2001:db8::")
    '2001:db8::/64'
    >>> parse_network("::ffff:192.0.2.0")
    '192.0.2.0/24'
    >>> parse_network("::ffff:c000:200")
    Traceback (most recent call last):
    AssertionError: IPv4-mapped IPv6 addresses must be in dotted representation
    """
    if addr.startswith("::ffff:"):
        assert (
            "." in addr
        ), "IPv4-mapped IPv6 addresses must be in dotted representation"
        return f"{addr[7:]}/{prefix_len_v4}"
    return f"{addr}/{prefix_len_v6}"
