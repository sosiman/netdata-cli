"""netdata-cli — CLI entry point."""

from __future__ import annotations

import sys

import click

from . import __version__
from .client import NetdataClient, NetdataError
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


def _handle_error(exc: NetdataError) -> None:
    msg = f"Error: {exc}"
    if console:
        console.print(f"[bold red]{msg}[/]")
    else:
        print(msg, file=sys.stderr)
    sys.exit(1)


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
    """netdata-cli — A powerful CLI for the Netdata Agent REST API.

    Query metrics, charts, alarms, functions, and agent info from the
    command line.  Supports rich tables, JSON output, and time filtering.

    Set NETDATA_URL env var to change the default agent address.
    """
    ctx.ensure_object(dict)
    ctx.obj["client"] = _client(url, timeout)
    ctx.obj["as_json"] = as_json


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

            # type filter
            if chart_type and info.get("type", "") != chart_type:
                continue

            # text search
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

        # sort by status severity
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

        # Normalize — API returns dict with 'alarms' key or a list
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
                    # Show summary
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


# ------------------------------------------------------------------
# Top-level entry
# ------------------------------------------------------------------

def main() -> None:
    cli()


if __name__ == "__main__":
    main()
