"""Tests for the NetdataClient."""

import pytest

from netdata_cli.client import NetdataClient, NetdataError


class TestNetdataClient:
    def test_init_defaults(self):
        c = NetdataClient()
        assert c.base_url == "http://localhost:19999"
        assert c.timeout == 10

    def test_init_custom_url(self):
        c = NetdataClient(base_url="http://myhost:20000/")
        assert c.base_url == "http://myhost:20000"

    def test_ping_failure(self):
        c = NetdataClient(base_url="http://localhost:1", timeout=1)
        assert c.ping() is False
