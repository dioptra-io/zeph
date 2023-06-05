# 🌬️ Zeph

[![Tests](https://img.shields.io/github/actions/workflow/status/dioptra-io/zeph/tests.yml?logo=github)](https://github.com/dioptra-io/zeph/actions/workflows/tests.yml)
[![Coverage](https://img.shields.io/codecov/c/github/dioptra-io/zeph?logo=codecov&logoColor=white)](https://app.codecov.io/gh/dioptra-io/zeph)
[![PyPI](https://img.shields.io/pypi/v/dioptra-zeph?color=blue&logo=pypi&logoColor=white)](https://pypi.org/project/dioptra-zeph/)

> Zeph is a reinforcement learning based algorithm for selecting prefixes to probe based on previous measurements in order to maximize the number of nodes and links discovered. Zeph can be used on top of the [Iris](https://iris.dioptra.io) platform.


## 🚀 Quickstart

Zeph has a command line interface to configure and run the algorithm.

First, install the Zeph package:

```
pip install dioptra-zeph
```

Zeph takes as input a list of /24 (IPv4) or /64 (IPv6) prefixes:
```sh
# prefixes.txt
8.8.8.0/24
2001:4860:4860::/64
```

To start a measurement from scratch:
```bash
zeph prefixes.txt
```

To start from a previous measurement:
```bash
zeph prefixes.txt UUID
```

Zeph relies on [iris-client](https://github.com/dioptra-io/iris-client) and [pych-client](https://github.com/dioptra-io/pych-client)
for communicating with Iris and ClickHouse. See their respective documentation to know how to specify the credentials.

## ✨ Generate prefix lists from BGP RIBs

You can create an _exhaustive_ list of /24 prefixes from a BGP RIB dump:
```bash
pyasn_util_download.py --latest
# Connecting to ftp://archive.routeviews.org
# Finding most recent archive in /bgpdata/2022.05/RIBS ...
# Downloading ftp://archive.routeviews.org//bgpdata/2022.05/RIBS/rib.20220524.1000.bz2
#  100%, 659KB/s
# Download complete.
zeph-bgp-convert --print-progress rib.20220524.1000.bz2 prefixes.txt
```

## 📚 Publications

```bibtex
@article{10.1145/3523230.3523232,
    author = {Gouel, Matthieu and Vermeulen, Kevin and Mouchet, Maxime and Rohrer, Justin P. and Fourmaux, Olivier and Friedman, Timur},
    title = {Zeph &amp; Iris Map the Internet: A Resilient Reinforcement Learning Approach to Distributed IP Route Tracing},
    year = {2022},
    issue_date = {January 2022},
    publisher = {Association for Computing Machinery},
    address = {New York, NY, USA},
    volume = {52},
    number = {1},
    issn = {0146-4833},
    url = {https://doi.org/10.1145/3523230.3523232},
    doi = {10.1145/3523230.3523232},
    journal = {SIGCOMM Comput. Commun. Rev.},
    month = {mar},
    pages = {2–9},
    numpages = {8},
    keywords = {active internet measurements, internet topology}
}
```

## 🧑‍💻 Authors

Iris is developed and maintained by the [Dioptra group](https://dioptra.io) at [Sorbonne Université](https://www.sorbonne-universite.fr) in Paris, France.
