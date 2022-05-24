# 🌬️ Zeph

[![Tests](https://img.shields.io/github/workflow/status/dioptra-io/zeph/Tests?logo=github)](https://github.com/dioptra-io/zeph/actions/workflows/tests.yml)
[![Coverage](https://img.shields.io/codecov/c/github/dioptra-io/zeph?logo=codecov&logoColor=white)](https://app.codecov.io/gh/dioptra-io/zeph)
[![PyPI](https://img.shields.io/pypi/v/dioptra-zeph?color=blue&logo=pypi&logoColor=white)](https://pypi.org/project/dioptra-zeph/)

> Zeph is a reinforcement learning based algorithm for selecting prefixes to probe based on previous measurements in order to maximize the number of nodes and links discovered. Zeph can be used on top of the [Iris](https://iris.dioptra.io) platform.


## 🚀 Quickstart

Zeph has a command line interface to configure and run the algorithm.

```
pip install dioptra-zeph
zeph --help
```

## ✨ Generate the BGP prefix file

Zeph needs to know the set of BGP prefixes that it can probe.
You can create a BGP prefix file by downloading the latest RIB from [routeviews.org](http://routeviews.org) and then convert it into a pickle file.

The easiest way to do that is to use the command line tools located in the `utils/` folder.

### Download the RIB

`zeph-bgp-download`

```
Usage: zeph_bgp_download.py [OPTIONS]

Options:
  --latestv4 / --no-latestv4      [default: False]
  --latestv6 / --no-latestv6      [default: False]
  --filepath PATH
  --install-completion [bash|zsh|fish|powershell|pwsh]
                                  Install completion for the specified shell.
  --show-completion [bash|zsh|fish|powershell|pwsh]
                                  Show completion for the specified shell, to
                                  copy it or customize the installation.

  --help                          Show this message and exit.
  ```

### Convert the RIB to a pickle file

`zeph-bgp-convert`

```
Usage: zeph_bgp_convert.py [OPTIONS] ROUTEVIEWS_FILEPATH

Arguments:
  ROUTEVIEWS_FILEPATH  [required]

Options:
  --bgp-prefixes-path PATH
  --excluded-prefixes-path PATH
  --install-completion [bash|zsh|fish|powershell|pwsh]
                                  Install completion for the specified shell.
  --show-completion [bash|zsh|fish|powershell|pwsh]
                                  Show completion for the specified shell, to
                                  copy it or customize the installation.

  --help                          Show this message and exit.
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
