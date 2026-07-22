"""Netdata MCP client — JSON-RPC 2.0 over HTTP."""

from __future__ import annotations

import json
from typing import Any

import requests


class MCPError(Exception):
    """Error communicating with Netdata MCP server."""


class MCPClient:
    """Thin wrapper around the Netdata MCP server (JSON-RPC 2.0)."""

    def __init__(self, base_url: str = "http://localhost:19999", timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.mcp_url = f"{self.base_url}/mcp"
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})
        self._id = 0

    def _call(self, method: str, params: dict | None = None) -> Any:
        """Make a JSON-RPC 2.0 call to the MCP server."""
        self._id += 1
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": self._id,
            "method": method,
        }
        if params is not None:
            payload["params"] = params

        try:
            resp = self._session.post(
                self.mcp_url,
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.ConnectionError:
            raise MCPError(
                f"Cannot connect to MCP at {self.mcp_url}. "
                "Is Netdata running and MCP enabled?"
            )
        except requests.Timeout:
            raise MCPError(f"MCP request timed out after {self.timeout}s")
        except requests.HTTPError as exc:
            raise MCPError(f"MCP HTTP error: {exc}")
        except (ValueError, json.JSONDecodeError):
            raise MCPError(f"Invalid JSON from MCP at {self.mcp_url}")

        if "error" in data:
            err = data["error"]
            msg = err.get("message", "Unknown MCP error")
            raise MCPError(f"MCP error: {msg}")

        return data.get("result", {})

    # ------------------------------------------------------------------
    # Server info
    # ------------------------------------------------------------------

    def initialize(self) -> dict:
        """Initialize MCP session and get server capabilities."""
        return self._call("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "netdata-cli", "version": "1.0"},
        })

    def ping(self) -> bool:
        """Check if MCP server is reachable."""
        try:
            result = self._call("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "netdata-cli", "version": "1.0"},
            })
            return bool(result.get("serverInfo"))
        except MCPError:
            return False

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    def list_tools(self) -> list[dict]:
        """List available MCP tools."""
        result = self._call("tools/list", {})
        return result.get("tools", [])

    def call_tool(self, name: str, arguments: dict | None = None) -> Any:
        """Call an MCP tool by name with arguments."""
        result = self._call("tools/call", {
            "name": name,
            "arguments": arguments or {},
        })
        # Extract text content from MCP response
        content = result.get("content", [])
        for item in content:
            if item.get("type") == "text":
                text = item.get("text", "")
                try:
                    return json.loads(text)
                except (ValueError, json.JSONDecodeError):
                    return text
        return content

    # ------------------------------------------------------------------
    # High-level wrappers for each MCP tool
    # ------------------------------------------------------------------

    def list_metrics(self, q: str = "", nodes: list[str] | None = None) -> Any:
        """Search available metrics by pattern or full-text query."""
        args: dict[str, Any] = {}
        if q:
            args["q"] = q
        if nodes:
            args["nodes"] = nodes
        return self.call_tool("list_metrics", args)

    def get_metrics_details(self, metrics: list[str], nodes: list[str] | None = None) -> Any:
        """Get comprehensive metadata for specific metrics."""
        args: dict[str, Any] = {"metrics": metrics}
        if nodes:
            args["nodes"] = nodes
        return self.call_tool("get_metrics_details", args)

    def list_nodes(self, metrics: list[str] | None = None) -> Any:
        """List all monitored nodes."""
        args: dict[str, Any] = {}
        if metrics:
            args["metrics"] = metrics
        return self.call_tool("list_nodes", args)

    def get_nodes_details(self, nodes: list[str] | None = None) -> Any:
        """Get comprehensive node information."""
        args: dict[str, Any] = {}
        if nodes:
            args["nodes"] = nodes
        return self.call_tool("get_nodes_details", args)

    def list_functions(self, nodes: list[str] | None = None) -> Any:
        """List available Netdata functions."""
        args: dict[str, Any] = {}
        if nodes:
            args["nodes"] = nodes
        return self.call_tool("list_functions", args)

    def execute_function(
        self,
        function_name: str,
        nodes: list[str] | None = None,
        after: int = 0,
        before: int = 0,
    ) -> Any:
        """Execute a Netdata function (processes, connections, etc)."""
        args: dict[str, Any] = {"function": function_name}
        if nodes:
            args["nodes"] = nodes
        if after:
            args["after"] = after
        if before:
            args["before"] = before
        return self.call_tool("execute_function", args)

    def query_metrics(
        self,
        metric: str,
        dimensions: list[str] | None = None,
        nodes: list[str] | None = None,
        after: int = -300,
        before: int = 0,
        points: int = 20,
        time_group: str = "average",
        group_by: list[str] | None = None,
        aggregation: str = "average",
        cardinality_limit: int = 10,
    ) -> Any:
        """Query time-series metrics data with aggregation."""
        args: dict[str, Any] = {
            "metric": metric,
            "after": after,
            "before": before,
            "points": points,
            "time_group": time_group,
            "aggregation": aggregation,
            "cardinality_limit": cardinality_limit,
        }
        if dimensions:
            args["dimensions"] = dimensions
        if nodes:
            args["nodes"] = nodes
        if group_by:
            args["group_by"] = group_by
        return self.call_tool("query_metrics", args)

    def find_correlated_metrics(
        self,
        after: int = -3600,
        before: int = 0,
        nodes: list[str] | None = None,
    ) -> Any:
        """Find metrics that changed significantly during a time period."""
        args: dict[str, Any] = {"after": after, "before": before}
        if nodes:
            args["nodes"] = nodes
        return self.call_tool("find_correlated_metrics", args)

    def find_anomalous_metrics(
        self,
        after: int = -3600,
        before: int = 0,
        nodes: list[str] | None = None,
    ) -> Any:
        """Find metrics detected as anomalous by ML models."""
        args: dict[str, Any] = {"after": after, "before": before}
        if nodes:
            args["nodes"] = nodes
        return self.call_tool("find_anomalous_metrics", args)

    def find_unstable_metrics(
        self,
        after: int = -3600,
        before: int = 0,
        nodes: list[str] | None = None,
    ) -> Any:
        """Find metrics with highest variability."""
        args: dict[str, Any] = {"after": after, "before": before}
        if nodes:
            args["nodes"] = nodes
        return self.call_tool("find_unstable_metrics", args)

    def list_raised_alerts(self, nodes: list[str] | None = None) -> Any:
        """List currently active alerts (WARNING/CRITICAL)."""
        args: dict[str, Any] = {}
        if nodes:
            args["nodes"] = nodes
        return self.call_tool("list_raised_alerts", args)

    def list_running_alerts(self, nodes: list[str] | None = None) -> Any:
        """List all alerts including cleared and uninitialized."""
        args: dict[str, Any] = {}
        if nodes:
            args["nodes"] = nodes
        return self.call_tool("list_running_alerts", args)

    def list_alert_transitions(
        self,
        after: int = -3600,
        before: int = 0,
        nodes: list[str] | None = None,
    ) -> Any:
        """List recent alert state transitions."""
        args: dict[str, Any] = {"after": after, "before": before}
        if nodes:
            args["nodes"] = nodes
        return self.call_tool("list_alert_transitions", args)
