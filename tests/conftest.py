"""Fixtures and imports for tests.

Home Assistant is not installed in the test environment, so we load
api.py and state.py directly instead of importing the full integration.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "panasonic_smart_laundry"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _import_module(name: str):
    package = "panasonic_smart_laundry"
    if package not in sys.modules:
        pkg = types.ModuleType(package)
        pkg.__path__ = [str(COMPONENT)]
        sys.modules[package] = pkg

    full_name = f"{package}.{name}"
    if full_name in sys.modules:
        return sys.modules[full_name]

    path = COMPONENT / f"{name}.py"
    spec = importlib.util.spec_from_file_location(full_name, path)
    module = importlib.util.module_from_spec(spec)

    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


api = _import_module("api")
state = _import_module("state")
const = _import_module("const")

Api = api.PanasonicSmartLaundryApi

parse_status = Api._parse_status_response
normalize_id = api._normalize_prop_id
normalize_value = api._normalize_prop_value
parse_remaining_time = state.parse_remaining_time
build_device_data = state.build_device_data
is_device_running = state.is_device_running


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

@pytest.fixture
def status():
    """Raw /device/status/ response captured from a NA-VX9800."""
    return load_fixture("status_econavi.json")


@pytest.fixture
def parsed(status):
    """Status response converted to a property map."""
    return parse_status(status)


@pytest.fixture
def device(status):
    """Device metadata from /device/info for label lookup."""
    return load_fixture("device_info_na_vx9800.json")["devices"][0]
