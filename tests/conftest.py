"""
Shared fixtures and helpers for all WindRouter test suites.
"""
import math
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import numpy as np
import pytest

# Stub pygrib (C extension) before any grib import
if "pygrib" not in sys.modules:
    sys.modules["pygrib"] = MagicMock()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def make_weather_cache(
    lats_1d=None,
    lons_1d=None,
    u_speed=5.0,
    v_speed=0.0,
    n_times=3,
    base_time=None,
):
    """
    Minimal in-memory weather_cache that mimics load_grib_to_memory output.

    Default grid: 4×4, 53–54°N / 2–3°E at 0.25° spacing.
    Default wind: 5 m/s westerly (~9.7 kt) — always safe.
    """
    if lats_1d is None:
        lats_1d = [53.0, 53.25, 53.5, 53.75]
    if lons_1d is None:
        lons_1d = [2.0, 2.25, 2.5, 2.75]
    if base_time is None:
        base_time = datetime(2026, 4, 20, 0, 0)

    rows, cols = len(lats_1d), len(lons_1d)
    lats_2d = np.array([[lat for _ in lons_1d] for lat in lats_1d], dtype=float)
    lons_2d = np.array([[lon for lon in lons_1d] for _ in lats_1d], dtype=float)
    u_arr = np.full((rows, cols), u_speed, dtype=float)
    v_arr = np.full((rows, cols), v_speed, dtype=float)
    dates = [base_time + timedelta(hours=i * 6) for i in range(n_times)]
    data = {
        dt: {
            "10 metre U wind component": u_arr.copy(),
            "10 metre v wind component": v_arr.copy(),
        }
        for dt in dates
    }
    return {"data": data, "dates": sorted(dates), "lats": lats_2d, "lons": lons_2d}


def make_safe_points_map(lats_1d, lons_1d):
    """Build safe_points_map directly without calling identify_safe_sailing_areas."""
    return {
        (r, c): {"lat": lat, "lon": lon, "max_speed": 9.7}
        for r, lat in enumerate(lats_1d)
        for c, lon in enumerate(lons_1d)
    }


def make_full_adjacency(safe_points_map, cost=1.0):
    """
    Fully-connected adjacency_map (every node to its Moore neighbors, uniform cost).
    For unit testing only.
    """
    adj = {node: [] for node in safe_points_map}
    for (r, c) in safe_points_map:
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                neighbor = (r + dr, c + dc)
                if neighbor in safe_points_map:
                    adj[(r, c)].append({"target": neighbor, "cost": cost})
    return adj


def make_mock_grib_message(name, valid_date, values, lats, lons):
    """Build a MagicMock mimicking a single pygrib message."""
    msg = MagicMock()
    msg.validDate = valid_date
    msg.name = name
    msg.values = values
    msg.latlons.return_value = (lats, lons)
    return msg
