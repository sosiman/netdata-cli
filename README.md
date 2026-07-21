# netdata-cli

A powerful CLI for the [Netdata](https://www.netdata.cloud/) Agent REST API.

Query metrics, charts, alarms, functions, and agent info — all from the terminal.
Rich table output, JSON mode, time filtering, and search built-in.

```
┌─────────────────────────────────────────────┐
│            Netdata Agent                     │
│  Version   v2.10.4                          │
│  OS        Debian GNU/Linux 13 (trixie)     │
│  Kernel    Linux 6.8.0-136-generic          │
│  CPU Cores 4                                │
│  RAM       15.4 GiB                         │
│  Charts    1669                             │
│  Metrics   4124                             │
│  Alarms OK 603                              │
└─────────────────────────────────────────────┘
```

## Installation

```bash
pip install netdata-cli
```

Or from source:

```bash
git clone https://github.com/sosi/netdata-cli
cd netdata-cli
pip install -e .
```

## Quick Start

```bash
# Agent info
nd info

# Check connectivity
nd ping

# Search charts
nd charts cpu
nd charts --type disk

# Get historical data
nd data system.cpu --after -300 --points 10
nd data mem.available --after -3600

# Alarms
nd alarms
nd alarms --active-only
nd alarm-log --after 86400

# Functions
nd functions
nd function docker:container-ls
nd function mount-points
nd function network-interfaces

# Collectors
nd collectors

# Raw JSON output
nd --json info
nd --json charts
```

## Commands

| Command | Description |
|---|---|
| `nd info` | Agent version, OS, CPU, RAM, chart/alarm counts, collectors |
| `nd ping` | Check if the agent is reachable |
| `nd charts [QUERY]` | List or search charts by id, title, type, units, dimensions |
| `nd chart CHART_ID` | Show chart details (dimensions, metadata, history) |
| `nd data CHART_ID` | Fetch historical data points with time range and grouping |
| `nd alarms` | List health alarms (active or all) |
| `nd alarm-log` | Alarm history with time filtering |
| `nd allmetrics` | Snapshot of every metric (JSON, shell, or Prometheus format) |
| `nd function NAME` | Call Netdata functions (docker, systemd, network, etc.) |
| `nd functions` | List available functions |
| `nd collectors` | List active data collectors |

## Configuration

Set the `NETDATA_URL` environment variable to point to a remote agent:

```bash
export NETDATA_URL=http://my-server:19999
nd info
```

Or pass `--url` on every call:

```bash
nd --url http://my-server:19999 charts
```

## Output Formats

Every command supports `--json` (`-j`) for raw JSON output, useful for piping to `jq`:

```bash
nd --json charts | jq '.[] | select(.units == "percentage")'
nd --json alarms | jq '.[] | select(.status == "WARNING")'
nd --json data system.cpu | jq '.data[-1]'
```

## Time Filtering

The `--after` flag accepts negative seconds (relative to now):

| Value | Meaning |
|---|---|
| `-60` | Last minute |
| `-300` | Last 5 minutes |
| `-3600` | Last hour |
| `-86400` | Last 24 hours |
| `-604800` | Last 7 days |

Data granularity depends on the chart's `update_every` setting and the Netdata database retention.

## Examples

### Monitor CPU in real-time

```bash
watch -n 2 'nd data system.cpu --after -10 --points 10'
```

### Find all disk charts

```bash
nd charts disk
```

### Export all metrics as Prometheus

```bash
nd allmetrics --format prometheus
```

### Check only critical alarms

```bash
nd alarms --active-only
```

### List Docker containers via Netdata

```bash
nd function docker:container-ls
```

### Show network interfaces

```bash
nd function network-interfaces
```

## Requirements

- Python 3.10+
- A running Netdata agent (v1.x or v2.x)

## Dependencies

- [click](https://click.palletsprojects.com/) — CLI framework
- [requests](https://requests.readthedocs.io/) — HTTP client
- [rich](https://rich.readthedocs.io/) — Terminal formatting

## Development

```bash
git clone https://github.com/sosi/netdata-cli
cd netdata-cli
pip install -e ".[dev]"
pytest
ruff check .
```

## License

[MIT](LICENSE)
