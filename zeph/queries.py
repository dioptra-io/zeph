from dataclasses import dataclass

from diamond_miner.queries.fragments import IPNetwork
from diamond_miner.queries.query import (
    UNIVERSE_SUBSET,
    LinksQuery,
    ResultsQuery,
    links_table,
    results_table,
)


@dataclass(frozen=True)
class GetNodeDiscoveries(ResultsQuery):
    def statement(
        self, measurement_id: str, subset: IPNetwork = UNIVERSE_SUBSET
    ) -> str:
        return f"""
        SELECT
            probe_dst_prefix,
            probe_protocol,
            groupUniqArray(reply_src_addr) as discoveries
        FROM {results_table(measurement_id)}
        WHERE {self.filters(subset)}
        GROUP BY (probe_dst_prefix, probe_protocol)
        """


@dataclass(frozen=True)
class GetLinkDiscoveries(LinksQuery):
    def statement(
        self, measurement_id: str, subset: IPNetwork = UNIVERSE_SUBSET
    ) -> str:
        return f"""
        SELECT
            probe_dst_prefix,
            probe_protocol,
            groupUniqArray((near_addr,far_addr)) AS discoveries
        FROM {links_table(measurement_id)}
        WHERE {self.filters(subset)}
        GROUP BY (probe_dst_prefix, probe_protocol)
        """
