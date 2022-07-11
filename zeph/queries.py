from dataclasses import dataclass

from diamond_miner.defaults import UNIVERSE_SUBSET
from diamond_miner.queries.query import LinksQuery, links_table
from diamond_miner.typing import IPNetwork
from pych_client import ClickHouseClient

from zeph.typing import Agent, Link, Network
from zeph.utilities import measurement_id, parse_network


@dataclass(frozen=True)
class GetUniqueLinksByPrefix(LinksQuery):
    """
    Get the list of unique links per prefix.
    To make things faster, we only retrieve the hash of each link,
    since we do not need the actual IP addresses seen.
    """

    def statement(
        self, measurement_id: str, subset: IPNetwork = UNIVERSE_SUBSET
    ) -> str:
        return f"""
        SELECT
            probe_dst_prefix,
            groupUniqArray(cityHash64((near_addr, far_addr))) AS links
        FROM {links_table(measurement_id)}
        WHERE {self.filters(subset)}
        GROUP BY probe_dst_prefix
        """

    def for_all_agents(
        self, client: ClickHouseClient, measurement_uuid: str, agents_uuid: list[str]
    ) -> dict[tuple[Agent, Network], set[Link]]:
        links: dict[tuple[Agent, Network], set[Link]] = {}
        for agent_uuid in agents_uuid:
            for row in self.execute_iter(
                client, measurement_id(measurement_uuid, agent_uuid)
            ):
                network = parse_network(row["probe_dst_prefix"])
                links[(agent_uuid, network)] = set(row["links"])
        return links
