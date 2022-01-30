# 🌬️ Zeph

[![Tests](https://img.shields.io/github/workflow/status/dioptra-io/zeph/Tests?logo=github)](https://github.com/dioptra-io/zeph/actions/workflows/tests.yml)
[![Coverage](https://img.shields.io/codecov/c/github/dioptra-io/zeph?logo=codecov&logoColor=white)](https://app.codecov.io/gh/dioptra-io/zeph)
[![PyPI](https://img.shields.io/pypi/v/dioptra-zeph?color=blue&logo=pypi&logoColor=white)](https://pypi.org/project/dioptra-zeph/)

> Zeph is a reinforcement learning based algorithm for selecting prefixes to probe based on previous measurements in order to maximize the number of nodes and links discovered. Zeph can be used on top of the [Iris](https://iris.dioptra.io) platform.


## 🚀 Quickstart

Zeph has a command line interface to configure and run the algorithm.

First, create the Python virtual environment:

```
poetry install 
```

Then, execute `poetry run zeph`:

```
Usage: zeph.py [OPTIONS]

Options:
  --api-url TEXT                  [default: https://api.iris.dioptra.io]
  --api-username TEXT             [required]
  --api-password TEXT             [required]
  --database-url TEXT             [default:
                                  http://localhost:8123?database=iris]

  --bgp-prefixes-path PATH        [required]
  --agent-tag TEXT                [default: all]
  --tool TEXT                     [default: diamond-miner]
  --protocol TEXT                 [default: icmp]
  --min-ttl INTEGER               [default: 2]
  --max-ttl INTEGER               [default: 32]
  --epsilon FLOAT                 [default: 0.1]
  --previous-measurement-uuid UUID
  --fixed-budget INTEGER
  --dry-run / --no-dry-run        [default: False]
  --install-completion [bash|zsh|fish|powershell|pwsh]
                                  Install completion for the specified shell.
  --show-completion [bash|zsh|fish|powershell|pwsh]
                                  Show completion for the specified shell, to
                                  copy it or customize the installation.

  --help                          Show this message and exit.
```

## ✨ Generate the BGP prefix file 

Zeph needs to know the set of BGP prefixes that it can probe. 
You can create a BGP prefix file by downloading the latest RIB from [routeviews.org](http://routeviews.org) and then convert it into a pickle file.

The easiest way to do that is to use the command line tools located in the `utils/` folder.

### Download the RIB

`poetry run zeph-bgp-download`

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

`poetry run zeph-bgp-convert`

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

```
```

## 🧑‍💻 Authors

Iris is developed and maintained by the [Dioptra group](https://dioptra.io) at [Sorbonne Université](https://www.sorbonne-universite.fr) in Paris, France.
