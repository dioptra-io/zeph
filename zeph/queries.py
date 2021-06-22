from dataclasses import dataclass


from diamond_miner.queries.fragments import IPNetwork
from diamond_miner.queries.query import (
    UNIVERSE_SUBSET,
    ResultsQuery,
    LinksQuery,
    results_table,
    links_table,
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
            groupUniqArray({self.addr_cast('reply_src_addr')})
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
            groupUniqArray(
                (
                    {self.addr_cast('near_addr')},
                    {self.addr_cast('far_addr')}
                )
            )
        FROM {links_table(measurement_id)}
        WHERE {self.filters(subset)}
        GROUP BY (probe_dst_prefix, probe_protocol)
        """
