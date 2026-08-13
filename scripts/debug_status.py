#!/usr/bin/env python3
"""Fetch Panasonic laundry status and show how progress is calculated.

Usage:
  export ACCESS_TOKEN='...'
  export APPLIANCE_ID='tXWiIvuLUxWPEu3qNW9TqbKEWaqeXhrLGhyKFMdCjtk='
  uv run python scripts/debug_status.py
"""

from __future__ import annotations

import importlib.util
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "panasonic_smart_laundry"


def load_module(name: str):
    pkg = "panasonic_smart_laundry"
    if pkg not in sys.modules:
        pkg_mod = type(sys)(pkg)
        pkg_mod.__path__ = [str(COMPONENT)]
        sys.modules[pkg] = pkg_mod

    full_name = f"{pkg}.{name}"
    spec = importlib.util.spec_from_file_location(full_name, COMPONENT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


const = load_module("const")
state = load_module("state")
JST = timezone(timedelta(hours=9))


def main() -> None:
    token = os.environ.get("ACCESS_TOKEN")
    appliance_id = os.environ.get("APPLIANCE_ID")
    if not token or not appliance_id:
        raise SystemExit("Set ACCESS_TOKEN and APPLIANCE_ID environment variables.")

    ts = datetime.now(JST).strftime("%Y%m%d%H%M%S%z")
    base = "https://app.wad.apws.panasonic.com"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json",
        "X-Timestamp": ts,
        "X-ApplianceId": appliance_id,
        "X-VerifyAppliance": "true",
    }

    response = requests.get(
        f"{base}/laundry/v5/device/status/",
        headers=headers,
        timeout=30,
    )
    print(f"HTTP {response.status_code}")
    if response.status_code != 200:
        print(response.text[:500])
        raise SystemExit(1)

    props: dict[str, str] = {}
    for item in response.json().get("status") or []:
        prop_id = item.get("id")
        params = item.get("params") or []
        value = params[0].get("value") if params else item.get("value")
        if prop_id:
            props[prop_id] = value

    keys = ["0080", "0121", "00E2", "00D0", "00ED", "00DB", "00DC"]
    print("\nRaw properties:")
    for key in keys:
        raw = props.get(key)
        if key in {"00ED", "00DB", "00DC"}:
            parsed = state.parse_remaining_time(raw)
        else:
            parsed = raw
        print(f"  {key}: raw={raw!r} parsed={parsed}")

    data = state.build_device_data(props)
    running = state.is_device_running(data)
    for elapsed in (None, 0, 10):
        progress = state.compute_cycle_progress(
            data,
            running=running,
            elapsed_minutes=elapsed,
        )
        print(f"  progress(elapsed={elapsed})={progress}%")

    print("\nComputed:")
    print(f"  running={running}")
    print(f"  operation={data.operation} transition={data.transition}")
    print(f"  remaining_minutes={data.remaining_minutes}")


if __name__ == "__main__":
    main()
