from ipaddress import ip_network

from zeph.rankers import UniqueLinksRanker


def test_unique_ranker():
    ranker = UniqueLinksRanker()
    links = {
        ("a", ip_network("192.168.0.0/24")): {("1", "2")},
        ("a", ip_network("192.168.1.0/24")): {("1", "2"), ("2", "3")},
        ("a", ip_network("192.168.2.0/24")): {("1", "2"), ("3", "4")},
        ("b", ip_network("192.168.0.0/24")): {("1", "2")},
        ("b", ip_network("192.168.1.0/24")): {("5", "6"), ("7", "8")},
    }
    ranked = ranker(links)
    assert ranked["a"] == [ip_network("192.168.1.0/24"), ip_network("192.168.2.0/24")]
    assert ranked["b"] == [ip_network("192.168.1.0/24")]
