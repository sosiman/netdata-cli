---
name: netdata-cli
description: "Use when monitoring server metrics, checking alerts, querying CPU/RAM/disk/network, finding anomalous metrics, or investigating performance issues via Netdata. Wraps both REST API and MCP (ML-powered) backends."
version: 0.2.0
author: sosiman
license: MIT
metadata:
  hermes:
    tags: [monitoring, metrics, alerts, anomaly-detection, mcp, netdata, server, infrastructure]
    related_skills: [cli-factory]
---

# netdata-cli (nd) — Server Monitoring CLI

## Overview

CLI tool for the Netdata Agent. Two backends:
- **REST API** — charts, data, alarms, functions, collectors
- **MCP** — ML-powered anomaly detection, metric correlations, advanced querying

Install: `pip install netdata-cli`

## Quick Start

```bash
nd ping                          # check agent reachable
nd info                          # version, OS, charts, alarms
nd charts                        # list all charts
nd charts cpu                    # search charts by keyword
nd data system.cpu --after -60   # CPU data last 60s
nd alarms                        # active alarms
nd --json info | jq .version     # JSON output for scripts
```

## REST API Commands

| Command | Description | Example |
|---|---|---|
| `nd info` | Agent info (version, OS, charts, collectors) | `nd info` |
| `nd ping` | Check agent reachable | `nd ping` |
| `nd charts [QUERY]` | List/search charts | `nd charts disk` |
| `nd chart <ID>` | Chart details | `nd chart system.cpu` |
| `nd data <ID>` | Historical data | `nd data system.cpu --after -300 --points 10` |
| `nd alarms` | Active alarms | `nd alarms --active-only` |
| `nd alarm-log` | Alarm history | `nd alarm-log --after 3600` |
| `nd allmetrics` | Snapshot all metrics | `nd allmetrics --format prometheus` |
| `nd function <NAME>` | Call Netdata function | `nd function docker:container-ls` |
| `nd functions` | List available functions | `nd functions` |
| `nd collectors` | Active data collectors | `nd collectors` |

### Common Options (REST)

- `--after, -a N` — Start time, seconds from now (negative). Default: -60
- `--before, -b N` — End time (0=now). Default: 0
- `--points, -p N` — Number of data points. Default: 60
- `--group, -g METHOD` — Grouping: average, min, max, sum, incremental
- `--json, -j` — Output raw JSON (works on ALL commands)

## MCP Commands (ML-Powered)

All under `nd mcp`. Endpoint: `http://localhost:19999/mcp`

| Command | Description | Example |
|---|---|---|
| `nd mcp ping` | Check MCP server | `nd mcp ping` |
| `nd mcp list-tools` | List MCP tools available | `nd mcp list-tools` |
| `nd mcp nodes` | List monitored nodes | `nd mcp nodes` |
| `nd mcp nodes-details` | Node hardware/OS info | `nd mcp nodes-details` |
| `nd mcp metrics [QUERY]` | Search metrics by pattern | `nd mcp metrics "*nginx*"` |
| `nd mcp metrics-details <NAMES>` | Metric metadata | `nd mcp metrics-details system.cpu system.ram` |
| `nd mcp query <METRIC>` | Query with ML anomaly data | `nd mcp query system.cpu -d user -d system` |
| `nd mcp anomalies` | Find ML-detected anomalies | `nd mcp anomalies --after -3600` |
| `nd mcp correlated` | Metrics that changed significantly | `nd mcp correlated --after -300` |
| `nd mcp unstable` | Highest variability metrics | `nd mcp unstable --after -86400` |
| `nd mcp mcp-alerts` | Active alerts (WARNING/CRITICAL) | `nd mcp mcp-alerts` |
| `nd mcp all-alerts` | All alerts incl. cleared | `nd mcp all-alerts` |
| `nd mcp alert-history` | Alert state transitions | `nd mcp alert-history --after -86400` |
| `nd mcp mcp-functions` | Available functions | `nd mcp mcp-functions` |
| `nd mcp exec <FUNC>` | Execute function via MCP | `nd mcp exec processes` |

### MCP Query Options

```bash
nd mcp query <METRIC> [OPTIONS]
  -d, --dimensions TEXT    Specific dimensions (repeatable)
  -n, --node TEXT          Filter by node (repeatable)
  -a, --after INT          Start time (default: -300)
  -b, --before INT         End time (default: 0)
  -p, --points INT         Data points (default: 20)
  -g, --time-group TEXT    average|min|max|sum (default: average)
  --group-by TEXT          dimension|instance|node (default: dimension)
  --aggregation TEXT       average|sum|min|max (default: average)
  --cardinality-limit INT  Max items returned (default: 10)
```

**CRITICAL:** `nd mcp query` requires `-d` (dimensions). Use `nd mcp metrics` first to find available dimensions, then query with specific ones.

### MCP Anomaly Detection

```bash
# Find anomalous metrics in the last hour
nd mcp anomalies --after -3600

# Find metrics that changed significantly (compares vs 4x baseline)
nd mcp correlated --after -300

# Find most unstable metrics in last 24h
nd mcp unstable --after -86400

# Query specific metric with anomaly info
nd mcp query system.cpu -d user -d system --after -60
```

## Environment Variables

- `NETDATA_URL` — Netdata agent URL (default: `http://localhost:19999`)

## JSON Output

Every command supports `--json` for scripting:

```bash
nd --json info | jq .version
nd --json mcp nodes | jq '.nodes[].hostname'
nd --json mcp query system.cpu -d user -d system | jq '.summary.dimensions'
nd --json alarms | jq '.[] | select(.status == "CRITICAL")'
```

## Pitfalls

1. **MCP query requires ALL params** — metric, after, before, points, time_group, group_by (array), aggregation, cardinality_limit. Missing any = error.
2. **MCP query requires dimensions** — Use `nd mcp metrics` to discover, then `-d dim1 -d dim2`.
3. **MCP group_by must be array** — In CLI it's a repeatable option, internally sent as array.
4. **REST alarms vs MCP alerts** — `nd alarms` (REST) and `nd mcp mcp-alerts` (MCP) return different formats. MCP includes more metadata.
5. **Empty results** — MCP returns empty when no anomalies/alerts exist. This is normal, not an error.

## Agent Workflow

For investigating server issues:

1. `nd ping` + `nd mcp ping` — verify connectivity
2. `nd info` — check agent version and stats
3. `nd mcp anomalies --after -3600` — find ML-detected problems
4. `nd mcp correlated --after -300` — what changed recently
5. `nd mcp query <metric> -d <dim>` — drill into specific metric
6. `nd alarms` — check active alerts
7. `nd function processes` — live process list
8. `nd mcp exec network-connections` — live connections
