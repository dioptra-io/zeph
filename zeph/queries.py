from dataclasses import dataclass
from ipaddress import IPv6Address

from diamond_miner.defaults import UNIVERSE_SUBSET
from diamond_miner.queries.query import LinksQuery, links_table
from diamond_miner.typing import IPNetwork
from pych_client import ClickHouseClient

from zeph.typing import Agent, Link
from zeph.utilities import addr_to_network, measurement_id


@dataclass(frozen=True)
class GetUniqueLinksByPrefix(LinksQuery):
    def statement(
        self, measurement_id: str, subset: IPNetwork = UNIVERSE_SUBSET
    ) -> str:
        return f"""
        SELECT
            probe_protocol,
            probe_dst_prefix,
            groupUniqArray((near_addr,far_addr)) AS links
        FROM {links_table(measurement_id)}
        WHERE {self.filters(subset)}
        GROUP BY (probe_protocol, probe_dst_prefix)
        """

    def for_all_agents(
        self, client: ClickHouseClient, measurement_uuid: str, agents_uuid: list[str]
    ) -> dict[tuple[Agent, IPNetwork], set[Link]]:
        links = {}
        for agent_uuid in agents_uuid:
            for row in self.execute_iter(
                client, measurement_id(measurement_uuid, agent_uuid)
            ):
                dst_prefix = IPv6Address(row["probe_dst_prefix"])
                network = addr_to_network(dst_prefix)
                links[(agent_uuid, network)] = set(row["links"])
        return links
