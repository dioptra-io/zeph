# 🌬️ Zeph

> Zeph is a reinforcement learning based algorithm for selecting prefixes to probe based on previous measurement in order to maximize the overall discoveries of nodes and links. Zeph can be used on top of Iris system.


## 🚀 Quickstart


Zeph dispose of a command line interface to configure and run the algorithm.

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
  --previous-measurement-uuid UUID
  --epsilon FLOAT                 [default: 0.1]
  --dry-run / --no-dry-run        [default: False]
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
