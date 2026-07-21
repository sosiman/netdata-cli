"""Output formatters for netdata-cli."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any

try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text

    HAS_RICH = True
except ImportError:
    HAS_RICH = False

console = Console() if HAS_RICH else None


# ------------------------------------------------------------------
# Generic helpers
# ------------------------------------------------------------------


def print_json(data: Any, pretty: bool = True) -> None:
    """Print data as JSON."""
    kwargs = {"indent": 2, "default": str} if pretty else {"default": str}
    print(json.dumps(data, **kwargs))


def _human_bytes(n: float | int | None) -> str:
    if n is None:
        return "—"
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PiB"


def _human_duration(seconds: float | int | None) -> str:
    if seconds is None:
        return "—"
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds / 60:.0f}m"
    if seconds < 86400:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds / 86400:.1f}d"


def _ts_to_str(ts: int | float | None) -> str:
    if ts is None:
        return "—"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _colorize_severity(severity: str) -> str:
    if not HAS_RICH:
        return severity
    mapping = {
        "CRITICAL": "[bold red]CRITICAL[/]",
        "WARNING": "[bold yellow]WARNING[/]",
        "CLEAR": "[bold green]CLEAR[/]",
        "UNDEFINED": "[dim]UNDEFINED[/]",
        "REMOVED": "[dim]REMOVED[/]",
    }
    return mapping.get(severity.upper(), severity)


# ------------------------------------------------------------------
# Info
# ------------------------------------------------------------------


def print_info(data: dict, as_json: bool = False) -> None:
    if as_json:
        print_json(data)
        return

    alarms = data.get("alarms", {})
    rows = [
        ("Version", data.get("version", "?")),
        ("OS", data.get("container_os_name", data.get("os_name", "?"))),
        ("Kernel", f"{data.get('kernel_name', '?')} {data.get('kernel_version', '?')}"),
        ("Architecture", data.get("architecture", "?")),
        ("CPU Cores", data.get("cores_total", "?")),
        ("CPU Freq", f"{int(data.get('cpu_freq', 0)) / 1e6:.0f} MHz"),
        ("RAM", _human_bytes(int(data.get("ram_total", 0)))),
        ("Disk", _human_bytes(int(data.get("total_disk_space", 0)))),
        ("Container", data.get("container", "none")),
        ("Charts", data.get("charts-count", "?")),
        ("Metrics", data.get("metrics-count", "?")),
        ("Memory Mode", data.get("memory-mode", "?")),
        ("Alarms OK", alarms.get("normal", "?")),
        ("Alarms Warn", alarms.get("warning", "?")),
        ("Alarms Crit", alarms.get("critical", "?")),
        ("Cloud", "claimed" if data.get("agent-claimed") else "not claimed"),
        ("HTTPS", "yes" if data.get("https-enabled") else "no"),
        ("Collectors", len(data.get("collectors", []))),
    ]

    if HAS_RICH:
        t = Table(title="Netdata Agent", show_header=False, box=None, padding=(0, 2))
        t.add_column(style="bold cyan", min_width=14)
        t.add_column()
        for label, value in rows:
            t.add_row(label, str(value))
        console.print(t)
    else:
        for label, value in rows:
            print(f"  {label:14s}  {value}")


# ------------------------------------------------------------------
# Charts
# ------------------------------------------------------------------


def print_charts(charts: list[dict], as_json: bool = False) -> None:
    if as_json:
        print_json(charts)
        return

    if HAS_RICH:
        t = Table(title=f"Charts ({len(charts)})")
        t.add_column("Chart ID", style="cyan", max_width=45)
        t.add_column("Title", max_width=40)
        t.add_column("Type", style="dim")
        t.add_column("Units", style="green")
        t.add_column("Dims", justify="right")
        t.add_column("Family", style="dim")
        for c in charts:
            t.add_row(
                c.get("id", "?"),
                c.get("title", "")[:40],
                c.get("type", ""),
                c.get("units", ""),
                str(len(c.get("dimensions", {}))),
                c.get("family", ""),
            )
        console.print(t)
    else:
        print(f"  {'Chart ID':45s} {'Title':40s} {'Type':15s} {'Units':10s} Dims")
        print(f"  {'─' * 45} {'─' * 40} {'─' * 15} {'─' * 10} ────")
        for c in charts:
            dims = len(c.get("dimensions", {}))
            print(
                f"  {c.get('id',''):45s} {c.get('title','')[:40]:40s} "
                f"{c.get('type',''):15s} {c.get('units',''):10s} {dims:>4}"
            )
    print(f"\n  Total: {len(charts)} charts")


def print_chart_detail(data: dict, as_json: bool = False) -> None:
    if as_json:
        print_json(data)
        return

    if HAS_RICH:
        t = Table(title=data.get("id", "Chart"), show_header=False, box=None)
        t.add_column(style="bold cyan", min_width=14)
        t.add_column()
        for key in ("id", "name", "type", "family", "title", "units", "plugin", "module"):
            t.add_row(key, str(data.get(key, "—")))
        t.add_row("dimensions", str(len(data.get("dimensions", {}))))
        t.add_row("update_every", str(data.get("update_every", "—")))
        t.add_row("history", str(data.get("history", "—")))
        console.print(t)

        if data.get("dimensions"):
            dt = Table(title="Dimensions")
            dt.add_column("ID", style="cyan")
            dt.add_column("Name")
            dt.add_column("Algorithm")
            dt.add_column("Multiplier")
            dt.add_column("Divisor")
            for dim_id, dim_info in data["dimensions"].items():
                dt.add_row(
                    dim_id,
                    dim_info.get("name", ""),
                    dim_info.get("algorithm", ""),
                    str(dim_info.get("multiplier", "")),
                    str(dim_info.get("divisor", "")),
                )
            console.print(dt)
    else:
        for key in ("id", "name", "type", "family", "title", "units", "plugin", "module"):
            print(f"  {key:14s}  {data.get(key, '—')}")
        print(f"\n  Dimensions:")
        for dim_id, dim_info in data.get("dimensions", {}).items():
            print(f"    {dim_id}: {dim_info.get('name','')} ({dim_info.get('algorithm','')})")


# ------------------------------------------------------------------
# Data
# ------------------------------------------------------------------


def print_data(data: dict, as_json: bool = False) -> None:
    """Print /api/v1/data response."""
    if as_json:
        print_json(data)
        return

    labels = data.get("labels", [])
    rows = data.get("data", [])

    if HAS_RICH:
        t = Table(title=data.get("chart", "Data"))
        for label in labels:
            style = "cyan" if label == "time" else None
            t.add_column(label, style=style, justify="right")
        for row in rows[-20:]:  # last 20 rows
            formatted = []
            for i, val in enumerate(row):
                if labels[i] == "time":
                    formatted.append(_ts_to_str(val))
                elif isinstance(val, float):
                    formatted.append(f"{val:.2f}")
                else:
                    formatted.append(str(val) if val is not None else "—")
            t.add_row(*formatted)
        console.print(t)
        if len(rows) > 20:
            console.print(f"[dim]  ... showing last 20 of {len(rows)} points[/]")
    else:
        header = "  ".join(f"{l:>12s}" for l in labels)
        print(f"  {header}")
        for row in rows[-20:]:
            vals = []
            for i, val in enumerate(row):
                if labels[i] == "time":
                    vals.append(f"{_ts_to_str(val):>12s}")
                elif isinstance(val, float):
                    vals.append(f"{val:>12.2f}")
                else:
                    vals.append(f"{str(val) if val is not None else '—':>12s}")
            print(f"  {'  '.join(vals)}")
        if len(rows) > 20:
            print(f"  ... showing last 20 of {len(rows)} points")


# ------------------------------------------------------------------
# Alarms
# ------------------------------------------------------------------


def print_alarms(alarms: list[dict], as_json: bool = False) -> None:
    if as_json:
        print_json(alarms)
        return

    if HAS_RICH:
        t = Table(title=f"Alarms ({len(alarms)})")
        t.add_column("Chart", style="cyan", max_width=30)
        t.add_column("Name", max_width=30)
        t.add_column("Status", justify="center")
        t.add_column("Value", justify="right")
        t.add_column("Warning", justify="right", style="yellow")
        t.add_column("Critical", justify="right", style="red")
        t.add_column("Last Updated")
        for a in alarms:
            t.add_row(
                a.get("chart", "?"),
                a.get("name", "?"),
                _colorize_severity(a.get("status", "?")),
                str(a.get("value", "—")),
                str(a.get("warn", "—")),
                str(a.get("crit", "—")),
                _ts_to_str(a.get("last_updated")),
            )
        console.print(t)
    else:
        print(f"  {'Chart':30s} {'Name':30s} {'Status':10s} {'Value':>10s} {'Warn':>10s} {'Crit':>10s}")
        for a in alarms:
            print(
                f"  {a.get('chart',''):30s} {a.get('name',''):30s} "
                f"{a.get('status',''):10s} {str(a.get('value','—')):>10s} "
                f"{str(a.get('warn','—')):>10s} {str(a.get('crit','—')):>10s}"
            )
    print(f"\n  Total: {len(alarms)} alarms")


def print_alarm_log(entries: list[dict], as_json: bool = False) -> None:
    if as_json:
        print_json(entries)
        return

    if HAS_RICH:
        t = Table(title=f"Alarm Log ({len(entries)} entries)")
        t.add_column("Time", style="dim")
        t.add_column("Chart", style="cyan", max_width=30)
        t.add_column("Name", max_width=25)
        t.add_column("Status", justify="center")
        t.add_column("Old", justify="center")
        t.add_column("Value", justify="right")
        for e in entries[-50:]:
            t.add_row(
                _ts_to_str(e.get("when")),
                e.get("chart", "?"),
                e.get("name", "?"),
                _colorize_severity(e.get("status_new", e.get("status", "?"))),
                e.get("status_old", "—"),
                str(e.get("value", "—")),
            )
        console.print(t)
        if len(entries) > 50:
            console.print(f"[dim]  ... showing last 50 of {len(entries)} entries[/]")
    else:
        for e in entries[-30:]:
            print(
                f"  {_ts_to_str(e.get('when'))}  {e.get('chart',''):25s}  "
                f"{e.get('name',''):20s}  {e.get('status_new', e.get('status',''))}"
            )


# ------------------------------------------------------------------
# Functions
# ------------------------------------------------------------------


def print_function(data: Any, as_json: bool = False) -> None:
    """Generic function output."""
    if as_json:
        print_json(data)
        return
    print_json(data)
