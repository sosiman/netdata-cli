"""netdata-cli — CLI entry point.

Combines Netdata REST API commands with MCP (Model Context Protocol) tools.
"""

from __future__ import annotations

import json
import sys

import click

from . import __version__
from .client import NetdataClient, NetdataError
from .mcp_client import MCPClient, MCPError
from .formatters import (
    HAS_RICH,
    console,
    print_alarm_log,
    print_alarms,
    print_chart_detail,
    print_charts,
    print_data,
    print_function,
    print_info,
    print_json,
)


def _client(url: str, timeout: int) -> NetdataClient:
    return NetdataClient(base_url=url, timeout=timeout)


def _mcp_client(url: str, timeout: int) -> MCPClient:
    return MCPClient(base_url=url, timeout=timeout)


def _handle_error(exc: Exception) -> None:
    msg = f"Error: {exc}"
    if console:
        console.print(f"[bold red]{msg}[/]")
    else:
        print(msg, file=sys.stderr)
    sys.exit(1)


def _output(data, as_json: bool, title: str = "") -> None:
    """Output data as JSON or pretty-printed."""
    if as_json:
        print_json(data)
    elif HAS_RICH and isinstance(data, (dict, list)):
        console.print_json(json.dumps(data, default=str, ensure_ascii=False))
    else:
        print(json.dumps(data, indent=2, default=str, ensure_ascii=False))


# ------------------------------------------------------------------
# Root group
# ------------------------------------------------------------------


@click.group()
@click.version_option(version=__version__, prog_name="netdata-cli")
@click.option(
    "--url",
    "-u",
    envvar="NETDATA_URL",
    default="http://localhost:19999",
    show_default=True,
    help="Netdata agent URL.",
)
@click.option("--timeout", "-t", default=10, show_default=True, help="Request timeout in seconds.")
@click.option("--json", "-j", "as_json", is_flag=True, help="Output raw JSON.")
@click.pass_context
def cli(ctx: click.Context, url: str, timeout: int, as_json: bool) -> None:
    """netdata-cli — A powerful CLI for the Netdata Agent REST API + MCP.

    Query metrics, charts, alarms, functions, and agent info from the
    command line.  Supports rich tables, JSON output, and time filtering.

    REST API commands: info, ping, charts, chart, data, alarms, alarm-log,
                       allmetrics, function, functions, collectors

    MCP commands:      mcp list-tools, mcp nodes, mcp metrics, mcp query,
                       mcp anomalies, mcp correlated, mcp alerts, etc.

    Set NETDATA_URL env var to change the default agent address.
    """
    ctx.ensure_object(dict)
    ctx.obj["client"] = _client(url, timeout)
    ctx.obj["mcp_client"] = _mcp_client(url, timeout)
    ctx.obj["as_json"] = as_json


# ==================================================================
# REST API COMMANDS (existing)
# ==================================================================


# ------------------------------------------------------------------
# info
# ------------------------------------------------------------------


@cli.command()
@click.pass_context
def info(ctx: click.Context) -> None:
    """Show Netdata agent info (version, OS, charts, alarms, collectors)."""
    try:
        data = ctx.obj["client"].info()
        print_info(data, as_json=ctx.obj["as_json"])
    except NetdataError as exc:
        _handle_error(exc)


# ------------------------------------------------------------------
# ping
# ------------------------------------------------------------------


@cli.command()
@click.pass_context
def ping(ctx: click.Context) -> None:
    """Check if the Netdata agent is reachable."""
    try:
        ok = ctx.obj["client"].ping()
        if ok:
            msg = "pong ✓"
            if console:
                console.print(f"[bold green]{msg}[/]")
            else:
                print(msg)
        else:
            msg = "Agent not responding"
            if console:
                console.print(f"[bold red]{msg}[/]")
            else:
                print(msg)
            sys.exit(1)
    except NetdataError as exc:
        _handle_error(exc)


# ------------------------------------------------------------------
# charts
# ------------------------------------------------------------------


@cli.command()
@click.argument("query", required=False)
@click.option("--type", "-T", "chart_type", help="Filter by chart type (e.g. system, disk, cgroup).")
@click.option("--limit", "-n", default=0, help="Max charts to show (0 = all).")
@click.pass_context
def charts(ctx: click.Context, query: str | None, chart_type: str | None, limit: int) -> None:
    """List or search charts.

    With no arguments, lists all charts.  With QUERY, searches chart
    id, title, type, family, units, and dimension names.
    """
    try:
        raw = ctx.obj["client"].charts()
        items = raw.get("charts", {})

        results = []
        for chart_id, info in items.items():
            entry = {"id": chart_id, **info}

            if chart_type and info.get("type", "") != chart_type:
                continue

            if query:
                q = query.lower()
                searchable = " ".join(
                    [
                        chart_id,
                        info.get("name", ""),
                        info.get("type", ""),
                        info.get("family", ""),
                        info.get("title", ""),
                        info.get("units", ""),
                        info.get("plugin", ""),
                        info.get("module", ""),
                        " ".join(info.get("dimensions", {}).keys()),
                    ]
                ).lower()
                if q not in searchable:
                    continue

            results.append(entry)

        if limit > 0:
            results = results[:limit]

        print_charts(results, as_json=ctx.obj["as_json"])
    except NetdataError as exc:
        _handle_error(exc)


# ------------------------------------------------------------------
# chart (detail)
# ------------------------------------------------------------------


@cli.command()
@click.argument("chart_id")
@click.pass_context
def chart(ctx: click.Context, chart_id: str) -> None:
    """Show details for a specific chart (dimensions, metadata)."""
    try:
        data = ctx.obj["client"].chart(chart_id)
        print_chart_detail(data, as_json=ctx.obj["as_json"])
    except NetdataError as exc:
        _handle_error(exc)


# ------------------------------------------------------------------
# data
# ------------------------------------------------------------------


@cli.command()
@click.argument("chart_id")
@click.option("--after", "-a", default=-60, show_default=True, help="Start time (seconds from now, negative).")
@click.option("--before", "-b", default=0, show_default=True, help="End time (seconds from now, 0=now).")
@click.option("--points", "-p", default=60, show_default=True, help="Number of data points.")
@click.option("--group", "-g", default="average", show_default=True, help="Grouping: average, min, max, sum, incremental.")
@click.option("--options", "-o", default="", help="Extra options: seconds, jsonwrap, flip, percent.")
@click.pass_context
def data(
    ctx: click.Context,
    chart_id: str,
    after: int,
    before: int,
    points: int,
    group: str,
    options: str,
) -> None:
    """Fetch historical data for a chart.

    \b
    Examples:
      nd data system.cpu --after -300 --points 10
      nd data disk.util.sda --after -3600 --group max
      nd data mem.available --after -86400 --points 1440
    """
    try:
        result = ctx.obj["client"].data(
            chart_id=chart_id,
            after=after,
            before=before,
            points=points,
            group=group,
            options=options,
        )
        print_data(result, as_json=ctx.obj["as_json"])
    except NetdataError as exc:
        _handle_error(exc)


# ------------------------------------------------------------------
# alarms
# ------------------------------------------------------------------


@cli.command()
@click.option("--all", "-a", "show_all", is_flag=True, help="Include inactive alarms.")
@click.option("--active-only", is_flag=True, help="Show only WARNING/CRITICAL alarms.")
@click.pass_context
def alarms(ctx: click.Context, show_all: bool, active_only: bool) -> None:
    """List alarms (health checks).

    \b
    Examples:
      nd alarms              # active alarms
      nd alarms --all        # all including inactive
      nd alarms --active-only  # only warn/critical
    """
    try:
        data = ctx.obj["client"].alarms(all=show_all)
        alarm_list = []
        for alarm_id, info in data.get("alarms", {}).items():
            alarm_list.append({"id": alarm_id, **info})

        if active_only:
            alarm_list = [
                a for a in alarm_list
                if a.get("status", "").upper() in ("WARNING", "CRITICAL")
            ]

        severity_order = {"CRITICAL": 0, "WARNING": 1, "UNDEFINED": 2, "CLEAR": 3, "REMOVED": 4}
        alarm_list.sort(key=lambda a: severity_order.get(a.get("status", "").upper(), 5))

        print_alarms(alarm_list, as_json=ctx.obj["as_json"])
    except NetdataError as exc:
        _handle_error(exc)


# ------------------------------------------------------------------
# alarm-log
# ------------------------------------------------------------------


@cli.command("alarm-log")
@click.option("--after", "-a", default=0, show_default=True, help="Last N seconds (0 = all).")
@click.option("--unique", "-u", is_flag=True, help="One entry per alarm (latest status).")
@click.pass_context
def alarm_log(ctx: click.Context, after: int, unique: bool) -> None:
    """Show alarm history log.

    \b
    Examples:
      nd alarm-log               # all history
      nd alarm-log --after 3600  # last hour
      nd alarm-log --after 86400 --unique  # last 24h, latest per alarm
    """
    try:
        c = ctx.obj["client"]
        if unique:
            entries = c.alarm_log_unique(after=after if after else 0)
        else:
            entries = c.alarm_log(after=after if after else 0)

        if isinstance(entries, dict):
            entries = entries.get("alarms", [])
        if isinstance(entries, list):
            entries.sort(key=lambda e: e.get("when", 0), reverse=True)

        print_alarm_log(entries, as_json=ctx.obj["as_json"])
    except NetdataError as exc:
        _handle_error(exc)


# ------------------------------------------------------------------
# allmetrics
# ------------------------------------------------------------------


@cli.command()
@click.option("--format", "-f", "fmt", default="json", type=click.Choice(["json", "shell", "prometheus"]), show_default=True)
@click.pass_context
def allmetrics(ctx: click.Context, fmt: str) -> None:
    """Snapshot of every metric in one call.

    Use --format prometheus for Prometheus-compatible output.
    """
    try:
        data = ctx.obj["client"].allmetrics(format=fmt)
        if fmt == "json":
            if isinstance(data, dict):
                count = len(data)
                print(f"Metrics families: {count}")
                if ctx.obj["as_json"]:
                    print_json(data)
                else:
                    for name in sorted(data.keys())[:30]:
                        entry = data[name]
                        dims = entry.get("dimensions", {})
                        print(f"  {name}: {len(dims)} dims = {list(dims.values())[:3]}...")
                    if count > 30:
                        print(f"  ... and {count - 30} more")
            else:
                print_json(data)
        else:
            print(data)
    except NetdataError as exc:
        _handle_error(exc)


# ------------------------------------------------------------------
# function
# ------------------------------------------------------------------


@cli.command("function")
@click.argument("name")
@click.option("--after", "-a", default=0, help="Start time (seconds from now, negative) or 0.")
@click.option("--before", "-b", default=0, help="End time or 0 for now.")
@click.option("--points", "-p", default=0, help="Number of data points (0 = server default).")
@click.pass_context
def function_cmd(ctx: click.Context, name: str, after: int, before: int, points: int) -> None:
    """Call a Netdata function (systemd-journal, docker:container-ls, etc).

    \b
    Examples:
      nd function docker:container-ls
      nd function systemd-journal --after -3600
      nd function mount-points
      nd function network-interfaces
    """
    try:
        data = ctx.obj["client"].function(
            function_name=name,
            after=after,
            before=before,
            points=points,
        )
        print_function(data, as_json=ctx.obj["as_json"])
    except NetdataError as exc:
        _handle_error(exc)


# ------------------------------------------------------------------
# functions (list available)
# ------------------------------------------------------------------


@cli.command("functions")
@click.pass_context
def functions_list(ctx: click.Context) -> None:
    """List available Netdata functions."""
    try:
        data = ctx.obj["client"].info()
        funcs = data.get("functions", {})

        if ctx.obj["as_json"]:
            print_json(funcs)
            return

        if HAS_RICH:
            from rich.table import Table

            t = Table(title=f"Functions ({len(funcs)})")
            t.add_column("Name", style="cyan")
            t.add_column("Help", max_width=60)
            t.add_column("Tags", style="dim")
            t.add_column("Timeout", justify="right")
            for name, info in funcs.items():
                t.add_row(
                    name,
                    info.get("help", "")[:60],
                    ", ".join(info.get("tags", [])) if isinstance(info.get("tags"), list) else str(info.get("tags", "")),
                    str(info.get("timeout", "")),
                )
            console.print(t)
        else:
            for name, info in funcs.items():
                print(f"  {name}: {info.get('help', '')[:80]}")
    except NetdataError as exc:
        _handle_error(exc)


# ------------------------------------------------------------------
# collectors
# ------------------------------------------------------------------


@cli.command()
@click.pass_context
def collectors(ctx: click.Context) -> None:
    """List active data collectors."""
    try:
        data = ctx.obj["client"].info()
        colls = data.get("collectors", [])

        if ctx.obj["as_json"]:
            print_json(colls)
            return

        if HAS_RICH:
            from rich.table import Table

            t = Table(title=f"Collectors ({len(colls)})")
            t.add_column("Plugin", style="cyan")
            t.add_column("Module")
            for c in colls:
                t.add_row(c.get("plugin", "?"), c.get("module", "—"))
            console.print(t)
        else:
            for c in colls:
                mod = c.get("module", "")
                suffix = f" / {mod}" if mod else ""
                print(f"  {c.get('plugin', '?')}{suffix}")
    except NetdataError as exc:
        _handle_error(exc)


# ==================================================================
# MCP COMMANDS (new)
# ==================================================================


@cli.group()
@click.pass_context
def mcp(ctx: click.Context) -> None:
    """MCP (Model Context Protocol) commands — ML-powered analysis.

    These commands use Netdata's MCP server for anomaly detection,
    metric correlations, and advanced querying.
    """
    pass


# ------------------------------------------------------------------
# mcp ping
# ------------------------------------------------------------------


@mcp.command()
@click.pass_context
def ping(ctx: click.Context) -> None:
    """Check if MCP server is reachable."""
    try:
        ok = ctx.obj["mcp_client"].ping()
        if ok:
            msg = "MCP pong ✓"
            if console:
                console.print(f"[bold green]{msg}[/]")
            else:
                print(msg)
        else:
            msg = "MCP server not responding"
            if console:
                console.print(f"[bold red]{msg}[/]")
            else:
                print(msg)
            sys.exit(1)
    except MCPError as exc:
        _handle_error(exc)


# ------------------------------------------------------------------
# mcp list-tools
# ------------------------------------------------------------------


@mcp.command("list-tools")
@click.pass_context
def mcp_list_tools(ctx: click.Context) -> None:
    """List available MCP tools."""
    try:
        tools = ctx.obj["mcp_client"].list_tools()
        if ctx.obj["as_json"]:
            print_json(tools)
            return

        if HAS_RICH:
            from rich.table import Table

            t = Table(title=f"MCP Tools ({len(tools)})")
            t.add_column("Name", style="cyan")
            t.add_column("Description", max_width=70)
            for tool in tools:
                t.add_row(tool.get("name", "?"), tool.get("description", "")[:70])
            console.print(t)
        else:
            for tool in tools:
                print(f"  {tool.get('name', '?')}: {tool.get('description', '')[:80]}")
    except MCPError as exc:
        _handle_error(exc)


# ------------------------------------------------------------------
# mcp nodes
# ------------------------------------------------------------------


@mcp.command()
@click.option("--metrics", "-m", multiple=True, help="Filter nodes by metric name.")
@click.pass_context
def nodes(ctx: click.Context, metrics: tuple) -> None:
    """List monitored nodes."""
    try:
        data = ctx.obj["mcp_client"].list_nodes(list(metrics) if metrics else None)
        _output(data, ctx.obj["as_json"], "Nodes")
    except MCPError as exc:
        _handle_error(exc)


# ------------------------------------------------------------------
# mcp nodes-details
# ------------------------------------------------------------------


@mcp.command("nodes-details")
@click.option("--node", "-n", multiple=True, help="Node ID or hostname.")
@click.pass_context
def nodes_details(ctx: click.Context, node: tuple) -> None:
    """Get detailed node information (hardware, OS, capabilities)."""
    try:
        data = ctx.obj["mcp_client"].get_nodes_details(list(node) if node else None)
        _output(data, ctx.obj["as_json"], "Node Details")
    except MCPError as exc:
        _handle_error(exc)


# ------------------------------------------------------------------
# mcp metrics
# ------------------------------------------------------------------


@mcp.command()
@click.argument("query", required=False)
@click.option("--node", "-n", multiple=True, help="Filter by node.")
@click.pass_context
def metrics(ctx: click.Context, query: str | None, node: tuple) -> None:
    """Search available metrics (contexts).

    \b
    Examples:
      nd mcp metrics                     # list all
      nd mcp metrics "*nginx*"           # pattern search
      nd mcp metrics "q:mysql|redis"     # full-text search
    """
    try:
        q = query or ""
        if q.startswith("q:"):
            q = q[2:]
        data = ctx.obj["mcp_client"].list_metrics(
            q=q,
            nodes=list(node) if node else None,
        )
        _output(data, ctx.obj["as_json"], "Metrics")
    except MCPError as exc:
        _handle_error(exc)


# ------------------------------------------------------------------
# mcp metrics-details
# ------------------------------------------------------------------


@mcp.command("metrics-details")
@click.argument("metrics_names", nargs=-1, required=True)
@click.option("--node", "-n", multiple=True, help="Filter by node.")
@click.pass_context
def metrics_details(ctx: click.Context, metrics_names: tuple, node: tuple) -> None:
    """Get comprehensive metadata for specific metrics.

    \b
    Examples:
      nd mcp metrics-details system.cpu system.ram
      nd mcp metrics-details disk.util.* --node ubuntuserver
    """
    try:
        data = ctx.obj["mcp_client"].get_metrics_details(
            list(metrics_names),
            nodes=list(node) if node else None,
        )
        _output(data, ctx.obj["as_json"], "Metrics Details")
    except MCPError as exc:
        _handle_error(exc)


# ------------------------------------------------------------------
# mcp query
# ------------------------------------------------------------------


@mcp.command()
@click.argument("metric")
@click.option("--dimensions", "-d", multiple=True, help="Specific dimensions to query.")
@click.option("--node", "-n", multiple=True, help="Filter by node.")
@click.option("--after", "-a", default=-300, show_default=True, help="Start time (seconds from now).")
@click.option("--before", "-b", default=0, show_default=True, help="End time (0=now).")
@click.option("--points", "-p", default=20, show_default=True, help="Number of data points.")
@click.option("--time-group", "-g", default="average", show_default=True, help="Time grouping: average, min, max, sum.")
@click.option("--group-by", multiple=True, default=["dimension"], help="Group by: dimension, instance, node.")
@click.option("--aggregation", default="average", show_default=True, help="Aggregation: average, sum, min, max.")
@click.option("--cardinality-limit", default=10, show_default=True, help="Max items returned.")
@click.pass_context
def query(
    ctx: click.Context,
    metric: str,
    dimensions: tuple,
    node: tuple,
    after: int,
    before: int,
    points: int,
    time_group: str,
    group_by: tuple,
    aggregation: str,
    cardinality_limit: int,
) -> None:
    """Query time-series metrics with ML anomaly detection.

    \b
    Examples:
      nd mcp query system.cpu --after -60 --points 10
      nd mcp query system.ram -d used -d cached -d free
      nd mcp query disk.util.* --group-by dimension,node
      nd mcp query net.drops --after -3600 --aggregation sum
    """
    try:
        data = ctx.obj["mcp_client"].query_metrics(
            metric=metric,
            dimensions=list(dimensions) if dimensions else None,
            nodes=list(node) if node else None,
            after=after,
            before=before,
            points=points,
            time_group=time_group,
            group_by=list(group_by) if group_by else ["dimension"],
            aggregation=aggregation,
            cardinality_limit=cardinality_limit,
        )
        _output(data, ctx.obj["as_json"], f"Query: {metric}")
    except MCPError as exc:
        _handle_error(exc)


# ------------------------------------------------------------------
# mcp anomalies
# ------------------------------------------------------------------


@mcp.command()
@click.option("--after", "-a", default=-3600, show_default=True, help="Start time (seconds from now).")
@click.option("--before", "-b", default=0, show_default=True, help="End time (0=now).")
@click.option("--node", "-n", multiple=True, help="Filter by node.")
@click.pass_context
def anomalies(ctx: click.Context, after: int, before: int, node: tuple) -> None:
    """Find metrics detected as anomalous by ML models.

    \b
    Examples:
      nd mcp anomalies                    # last hour
      nd mcp anomalies --after -86400     # last 24h
      nd mcp anomalies --after -300       # last 5 min
    """
    try:
        data = ctx.obj["mcp_client"].find_anomalous_metrics(
            after=after,
            before=before,
            nodes=list(node) if node else None,
        )
        _output(data, ctx.obj["as_json"], "Anomalous Metrics")
    except MCPError as exc:
        _handle_error(exc)


# ------------------------------------------------------------------
# mcp correlated
# ------------------------------------------------------------------


@mcp.command()
@click.option("--after", "-a", default=-3600, show_default=True, help="Start time (seconds from now).")
@click.option("--before", "-b", default=0, show_default=True, help="End time (0=now).")
@click.option("--node", "-n", multiple=True, help="Filter by node.")
@click.pass_context
def correlated(ctx: click.Context, after: int, before: int, node: tuple) -> None:
    """Find metrics that changed significantly during a time period.

    Compares the specified window against a 4x earlier baseline.

    \b
    Examples:
      nd mcp correlated                    # last hour vs previous 4h
      nd mcp correlated --after -300       # last 5min vs previous 20min
    """
    try:
        data = ctx.obj["mcp_client"].find_correlated_metrics(
            after=after,
            before=before,
            nodes=list(node) if node else None,
        )
        _output(data, ctx.obj["as_json"], "Correlated Metrics")
    except MCPError as exc:
        _handle_error(exc)


# ------------------------------------------------------------------
# mcp unstable
# ------------------------------------------------------------------


@mcp.command()
@click.option("--after", "-a", default=-3600, show_default=True, help="Start time (seconds from now).")
@click.option("--before", "-b", default=0, show_default=True, help="End time (0=now).")
@click.option("--node", "-n", multiple=True, help="Filter by node.")
@click.pass_context
def unstable(ctx: click.Context, after: int, before: int, node: tuple) -> None:
    """Find metrics with highest variability (coefficient of variation).

    \b
    Examples:
      nd mcp unstable                     # last hour
      nd mcp unstable --after -86400      # last 24h
    """
    try:
        data = ctx.obj["mcp_client"].find_unstable_metrics(
            after=after,
            before=before,
            nodes=list(node) if node else None,
        )
        _output(data, ctx.obj["as_json"], "Unstable Metrics")
    except MCPError as exc:
        _handle_error(exc)


# ------------------------------------------------------------------
# mcp mcp-alerts
# ------------------------------------------------------------------


@mcp.command("mcp-alerts")
@click.option("--node", "-n", multiple=True, help="Filter by node.")
@click.pass_context
def mcp_alerts(ctx: click.Context, node: tuple) -> None:
    """List active alerts (WARNING/CRITICAL) via MCP."""
    try:
        data = ctx.obj["mcp_client"].list_raised_alerts(
            nodes=list(node) if node else None,
        )
        _output(data, ctx.obj["as_json"], "Active Alerts (MCP)")
    except MCPError as exc:
        _handle_error(exc)


# ------------------------------------------------------------------
# mcp all-alerts
# ------------------------------------------------------------------


@mcp.command("all-alerts")
@click.option("--node", "-n", multiple=True, help="Filter by node.")
@click.pass_context
def all_alerts(ctx: click.Context, node: tuple) -> None:
    """List all alerts including cleared and uninitialized."""
    try:
        data = ctx.obj["mcp_client"].list_running_alerts(
            nodes=list(node) if node else None,
        )
        _output(data, ctx.obj["as_json"], "All Alerts (MCP)")
    except MCPError as exc:
        _handle_error(exc)


# ------------------------------------------------------------------
# mcp alert-history
# ------------------------------------------------------------------


@mcp.command("alert-history")
@click.option("--after", "-a", default=-3600, show_default=True, help="Start time (seconds from now).")
@click.option("--before", "-b", default=0, show_default=True, help="End time (0=now).")
@click.option("--node", "-n", multiple=True, help="Filter by node.")
@click.pass_context
def alert_history(ctx: click.Context, after: int, before: int, node: tuple) -> None:
    """Show alert state transitions (history).

    \b
    Examples:
      nd mcp alert-history                    # last hour
      nd mcp alert-history --after -86400     # last 24h
    """
    try:
        data = ctx.obj["mcp_client"].list_alert_transitions(
            after=after,
            before=before,
            nodes=list(node) if node else None,
        )
        _output(data, ctx.obj["as_json"], "Alert History (MCP)")
    except MCPError as exc:
        _handle_error(exc)


# ------------------------------------------------------------------
# mcp functions
# ------------------------------------------------------------------


@mcp.command("mcp-functions")
@click.option("--node", "-n", multiple=True, help="Filter by node.")
@click.pass_context
def mcp_functions(ctx: click.Context, node: tuple) -> None:
    """List available Netdata functions via MCP."""
    try:
        data = ctx.obj["mcp_client"].list_functions(
            nodes=list(node) if node else None,
        )
        _output(data, ctx.obj["as_json"], "Functions (MCP)")
    except MCPError as exc:
        _handle_error(exc)


# ------------------------------------------------------------------
# mcp exec
# ------------------------------------------------------------------


@mcp.command("exec")
@click.argument("function_name")
@click.option("--node", "-n", multiple=True, help="Filter by node.")
@click.option("--after", "-a", default=0, help="Start time (seconds from now).")
@click.option("--before", "-b", default=0, help="End time (0=now).")
@click.pass_context
def mcp_exec(ctx: click.Context, function_name: str, node: tuple, after: int, before: int) -> None:
    """Execute a Netdata function via MCP.

    \b
    Examples:
      nd mcp exec processes
      nd mcp exec network-connections --node ubuntuserver
      nd mcp exec systemd-journal --after -3600
    """
    try:
        data = ctx.obj["mcp_client"].execute_function(
            function_name=function_name,
            nodes=list(node) if node else None,
            after=after,
            before=before,
        )
        _output(data, ctx.obj["as_json"], f"Function: {function_name}")
    except MCPError as exc:
        _handle_error(exc)


# ------------------------------------------------------------------
# Top-level entry
# ------------------------------------------------------------------

def main() -> None:
    cli()


if __name__ == "__main__":
    main()
