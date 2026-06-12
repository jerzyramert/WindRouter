"""
I/O contract tests for WindRouter — round-trip between grib.py and Visualiser.py.

These tests verify that files written by the routing engine (grib.py) can be
read correctly by the Visualiser (Visualiser.py). They simulate exactly what
Visualiser.py does when reading each file type.

Currently documented contracts:
  B-02: save_graph_to_json produces valid JSON readable by Visualiser (function works,
        just never called from __main__ — fix is to call it)
"""
import json
import os
from datetime import datetime, timedelta

import numpy as np
import pytest

from grib import save_graph_to_json, save_to_gpx
from conftest import make_weather_cache


class TestGraphJsonContract:
    """Round-trip: grib.py writes graph JSON, Visualiser reads it."""

    def test_b02_save_graph_to_json_is_callable_and_produces_valid_json(self, tmp_path):
        """B-02: save_graph_to_json is never called in __main__ — documents that
        the function exists and works correctly so calling it would fix B-02."""
        nodes = {(0, 0)}
        adj = {(0, 0): []}
        spm = {(0, 0): {"lat": 53.0, "lon": 2.0, "max_speed": 5.0}}
        json_path = str(tmp_path / "graph.json")

        save_graph_to_json(nodes, adj, spm, json_path)

        assert os.path.exists(json_path), "save_graph_to_json must create the file"
        with open(json_path) as fh:
            data = json.load(fh)
        assert "metadata" in data
        assert "nodes" in data
        assert data["metadata"]["nodes"] == 1
