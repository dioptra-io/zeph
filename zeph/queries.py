from dataclasses import dataclass


from diamond_miner.defaults import DEFAULT_PROBE_TTL_COLUMN
from diamond_miner.queries.fragments import IPNetwork
from diamond_miner.queries.query import DEFAULT_SUBSET, Query

# -- Old queries for discoveries


@dataclass(frozen=True)
class GetDiscoveriesFromResults(Query):
    def query(self, table: str, subset: IPNetwork = DEFAULT_SUBSET) -> str:
        return f"""
        WITH
        -- 1) Compute the links
        --  x.1             x.2            x.3            x.4       x.5            x.6
        -- (probe_dst_addr,probe_src_port,probe_dst_port,probe_ttl,reply_src_addr,round)
        groupUniqArray(
            (
                probe_dst_addr,
                probe_src_port,
                probe_dst_port,
                {DEFAULT_PROBE_TTL_COLUMN},
                IPv6NumToString(reply_src_addr),
                round
            )
        ) AS replies_unsorted,
        -- sort by (probe_dst_addr, probe_src_port, probe_dst_port, probe_ttl)
        arraySort(x -> (x.1, x.2, x.3, x.4), replies_unsorted) AS replies,
        -- shift by 1: remove the element and append a NULL row
        arrayConcat(
            arrayPopFront(replies), [(toIPv6('::'), 0, 0, 0, '', 0)]
        ) AS replies_shifted,
        -- compute the links by zipping the two arrays
        arrayFilter(
            x -> x.1.4 + 1 == x.2.4,
            arrayZip(replies, replies_shifted)
        ) AS links,
        arrayDistinct(arrayMap(x -> (x.1.5, x.2.5), links)) AS links_minimal,
        -- compute the nodes
        arrayDistinct(arrayMap(x->x.5, replies_unsorted)) as nodes,
        arrayDistinct(
            flatten(arrayMap(x-> [x.1, x.2], links_minimal))
        ) AS nodes_in_links,
        -- filter to get only the standalone nodes
        arrayFilter(x -> has(nodes_in_links, x) = 0, nodes) AS standalone_nodes,
        -- add the standalone nodes to the links
        arrayConcat(
            links_minimal,
            arrayMap(x -> (NULL, x), standalone_nodes)
        ) AS discoveries
        SELECT probe_dst_prefix,
               probe_protocol,
               discoveries
        FROM {table}
        WHERE {self.common_filters(subset)}
        GROUP BY (probe_protocol, probe_src_addr, probe_dst_prefix)
        """


@dataclass(frozen=True)
class GetFlowsPerDiscoveriesFromResults(Query):
    """
    Return the flows per discovery.

    >>> from diamond_miner.test import execute
    >>> execute(GetFlows(), 'test_nsdi_example')[0][0]
    """

    def query(self, table: str, subset: IPNetwork = DEFAULT_SUBSET) -> str:
        return f"""
        WITH
        -- 1) Compute the links
        --  x.1             x.2            x.3            x.4       x.5            x.6
        -- (probe_dst_addr,probe_src_port,probe_dst_port,probe_ttl,reply_src_addr,round)
        groupUniqArray(
            (
                IPv6NumToString(reply_src_addr),
                IPv6NumToString(probe_dst_addr),
                probe_src_port,
                probe_dst_port,
                {DEFAULT_PROBE_TTL_COLUMN},
                round
            )
        ) AS replies_unsorted,
        -- sort by (probe_dst_addr, probe_src_port, probe_dst_port, probe_ttl)
        arraySort(x -> (x.2, x.3, x.4, x.5), replies_unsorted) AS replies,
        -- shift by 1: remove the element and append a NULL row
        arrayConcat(arrayPopFront(replies), [('','', 0, 0, 0, 0)]) AS replies_shifted,
        -- compute the links by zipping the two arrays
        arrayFilter(
            x -> x.1.5 + 1 == x.2.5,
            arrayZip(replies, replies_shifted)
        ) AS links,
        -- compute the nodes
        arrayDistinct(arrayFlatten(arrayMap(x-> [x.1, x.2], links))) AS links_flat,
        arrayDistinct(arrayMap(x-> x.1, links_flat)) AS nodes_in_links,
        -- filter to get only the standalone nodes
        arrayFilter(
            x -> has(nodes_in_links, x.1) = 0, replies_unsorted
        ) AS standalone_nodes,
        -- add the standalone nodes to the links
        arrayConcat(
            links,
            arrayMap(x -> (('','',0,0,0,0), x), standalone_nodes)
        ) AS discoveries
        -- structure the discovery correctly
        SELECT probe_dst_prefix,
               probe_protocol,
               discoveries
        FROM {table}
        WHERE {self.common_filters(subset)}
        GROUP BY (probe_protocol, probe_src_addr, probe_dst_prefix)
        """


# -- Queries from results table


@dataclass(frozen=True)
class GetOneFlowPerNode(Query):
    def query(self, table: str, subset: IPNetwork = DEFAULT_SUBSET) -> str:
        return f"""
        SELECT {self.addr_cast('reply_src_addr')},
               probe_protocol,
               groupArray(
                   (
                       probe_dst_addr,
                       probe_src_port,
                       probe_dst_port,
                       {DEFAULT_PROBE_TTL_COLUMN}
                    )
                )[1]
        FROM {table}
        WHERE {self.common_filters(subset)}
        GROUP BY (probe_protocol, reply_src_addr)
        """


@dataclass(frozen=True)
class GetFlows(Query):
    def query(self, table: str, subset: IPNetwork = DEFAULT_SUBSET) -> str:
        return f"""
        -- structure the discovery correctly
        SELECT  {self.addr_cast('reply_src_addr')},
                {self.addr_cast('probe_dst_addr')},
                probe_src_port,
                probe_dst_port,
                {DEFAULT_PROBE_TTL_COLUMN},
                probe_protocol
        FROM {table}
        WHERE {self.common_filters(subset)}
        """


@dataclass(frozen=True)
class GetFlowsPerNode(Query):
    def query(self, table: str, subset: IPNetwork = DEFAULT_SUBSET) -> str:
        return f"""
        -- structure the discovery correctly
        SELECT  {self.addr_cast('reply_src_addr')},
                probe_dst_addr,
                probe_src_port,
                probe_dst_port,
                {DEFAULT_PROBE_TTL_COLUMN},
                probe_protocol
        FROM {table}
        WHERE {self.common_filters(subset)}
        """


# -- Queries from links table


@dataclass(frozen=True)
class GetDiscoveries(Query):
    # NOTE: remove `AND NOT is_inter_round` when present in the link table

    def query(self, table: str, subset: IPNetwork = DEFAULT_SUBSET) -> str:
        return f"""
        SELECT
            {self.addr_cast('probe_dst_prefix')},,
            probe_protocol,
            near_ttl,
            groupUniqArray(
                (
                    {self.addr_cast('near_addr')},
                    {self.addr_cast('far_addr')}
                )
            )
        FROM {table}
        WHERE NOT is_virtual AND NOT is_inter_round
        GROUP BY (probe_dst_prefix, probe_protocol, near_ttl)
        """


@dataclass(frozen=True)
class GetDiscoveriesPerPrefix(Query):
    # NOTE: remove `AND NOT is_inter_round` when present in the link table

    def query(self, table: str, subset: IPNetwork = DEFAULT_SUBSET) -> str:
        return f"""
        SELECT
            {self.addr_cast('probe_dst_prefix')},,
            groupUniqArray(
                (
                    {self.addr_cast('near_addr')},
                    {self.addr_cast('far_addr')}
                )
            )
        FROM {table}
        WHERE NOT is_virtual AND NOT is_inter_round
        GROUP BY (probe_dst_prefix)
        """


@dataclass(frozen=True)
class GetOneFLowPerLink(Query):
    # NOTE: remove `AND NOT is_inter_round` when present in the link table

    def query(self, table: str, subset: IPNetwork = DEFAULT_SUBSET) -> str:
        return f"""
        SELECT
            (CAST(near_addr AS String), CAST(far_addr AS String)),
            groupArray(
                (
                    probe_dst_addr,
                    probe_src_port,
                    probe_dst_port,
                    near_ttl,
                    probe_protocol
                )
            )[1]
        FROM {table}
        WHERE NOT is_virtual AND NOT is_partial AND NOT is_inter_round
        GROUP BY (near_addr, far_addr)
        """
