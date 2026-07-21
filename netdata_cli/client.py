"""Netdata REST API client."""

from __future__ import annotations

import time
from typing import Any

import requests


class NetdataError(Exception):
    """Error communicating with Netdata."""


class NetdataClient:
    """Thin wrapper around the Netdata REST API (v1)."""

    def __init__(self, base_url: str = "http://localhost:19999", timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/json"})

    # ------------------------------------------------------------------
    # Low-level
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict | None = None, raw: bool = False) -> Any:
        url = f"{self.base_url}{path}"
        try:
            resp = self._session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            if raw:
                return resp.text
            if not resp.content:
                return [] if "alarm_log" in path else {}
            return resp.json()
        except requests.ConnectionError:
            raise NetdataError(
                f"Cannot connect to Netdata at {self.base_url}. "
                "Is the agent running?"
            )
        except requests.Timeout:
            raise NetdataError(f"Request to {url} timed out after {self.timeout}s")
        except (requests.HTTPError, requests.exceptions.ChunkedEncodingError) as exc:
            raise NetdataError(f"HTTP error from {url}: {exc}")
        except ValueError:
            raise NetdataError(f"Invalid JSON response from {url}")

    # ------------------------------------------------------------------
    # Agent info
    # ------------------------------------------------------------------

    def info(self) -> dict:
        """Return /api/v1/info — agent version, OS, collectors, etc."""
        return self._get("/api/v1/info")

    # ------------------------------------------------------------------
    # Charts
    # ------------------------------------------------------------------

    def charts(self) -> dict:
        """Return all charts.  Response['charts'] is a dict keyed by chart id."""
        return self._get("/api/v1/charts")

    def chart(self, chart_id: str) -> dict:
        """Return details for a single chart."""
        return self._get("/api/v1/chart", params={"chart": chart_id})

    # ------------------------------------------------------------------
    # Data (historical)
    # ------------------------------------------------------------------

    def data(
        self,
        chart_id: str,
        after: int = -60,
        before: int = 0,
        points: int = 60,
        group: str = "average",
        format: str = "json",
        options: str = "",
    ) -> dict:
        """
        Fetch data points for *chart_id*.

        Parameters
        ----------
        after : int
            Seconds relative to now (negative) or unix timestamp.
        before : int
            Seconds relative to now (negative) or unix timestamp. 0 = now.
        points : int
            Number of data points to return.
        group : str
            Grouping method: average, min, max, sum, incremental, etc.
        format : str
            json | csv | tsv | ssv |Cumhurbaşkan
        options : str
            Comma-separated: seconds, jsonwrap, flip, min2max, percent, etc.
        """
        params: dict[str, Any] = {
            "chart": chart_id,
            "after": after,
            "before": before,
            "points": points,
            "group": group,
            "format": format,
        }
        if options:
            params["options"] = options
        return self._get("/api/v1/data", params=params)

    # ------------------------------------------------------------------
    # All metrics (snapshot)
    # ------------------------------------------------------------------

    def allmetrics(self, format: str = "json") -> dict | str:
        """Return a snapshot of every metric. format: json | shell | prometheus."""
        if format == "json":
            return self._get("/api/v1/allmetrics")
        # shell/prometheus return plain text
        return self._get(
            "/api/v1/allmetrics",
            params={"format": format, "help": "yes"},
            raw=True,
        )

    # ------------------------------------------------------------------
    # Alarms
    # ------------------------------------------------------------------

    def alarms(self, all: bool = False) -> dict:
        """Active alarms, or all (including inactive) if *all* is True."""
        path = "/api/v1/alarms"
        params = {"all": "yes"} if all else None
        return self._get(path, params=params)

    def alarm_log(self, after: int = 0) -> list:
        """Alarm log entries.  *after*: 0 = all, negative = last N seconds."""
        params = {}
        if after:
            params["after"] = after
        try:
            return self._get("/api/v1/alarm_log", params=params)
        except NetdataError:
            # Netdata returns empty chunked response when alarm log is empty
            return []

    def alarm_log_unique(self, after: int = 0) -> list:
        """Alarm log, one entry per unique alarm (latest status)."""
        params = {"all": "yes"}
        if after:
            params["after"] = after
        try:
            return self._get("/api/v1/alarm_log", params=params)
        except NetdataError:
            return []

    # ------------------------------------------------------------------
    # Functions (systemd-journal, docker:container-ls, etc.)
    # ------------------------------------------------------------------

    def function(
        self,
        function_name: str,
        context: str = "",
        after: int = 0,
        before: int = 0,
        points: int = 0,
        format: str = "json",
        options: str = "",
    ) -> Any:
        """Call a Netdata function (e.g. systemd-journal, docker:container-ls)."""
        params: dict[str, Any] = {"function": function_name}
        if context:
            params["context"] = context
        if after:
            params["after"] = after
        if before:
            params["before"] = before
        if points:
            params["points"] = points
        if format:
            params["format"] = format
        if options:
            params["options"] = options
        return self._get("/api/v1/function", params=params)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def search_charts(self, query: str) -> list[dict]:
        """Search charts by id, name, type, family, title, or units."""
        q = query.lower()
        raw = self.charts()
        results = []
        for chart_id, info in raw.get("charts", {}).items():
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
            if q in searchable:
                results.append({"id": chart_id, **info})
        return results

    def ping(self) -> bool:
        """Return True if the agent is reachable and ready."""
        try:
            data = self._get("/api/v1/info")
            return bool(data.get("version"))
        except NetdataError:
            return False
