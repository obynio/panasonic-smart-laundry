#!/usr/bin/env python3
"""Diagnose Panasonic API responses (token via ACCESS_TOKEN env var)."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

import requests

TOKEN = os.environ.get("ACCESS_TOKEN")
if not TOKEN:
    sys.exit("Set ACCESS_TOKEN")

JST = timezone(timedelta(hours=9))
BASE = "https://app.wad.apws.panasonic.com"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json;charset=UTF-8",
    "Accept": "application/json",
    "X-Timestamp": datetime.now(JST).strftime("%Y%m%d%H%M%S%z"),
}


def call(method: str, path: str, **kwargs) -> tuple[int, object]:
    resp = requests.request(method, f"{BASE}{path}", headers=HEADERS, timeout=30, **kwargs)
    try:
        body = resp.json()
    except Exception:
        body = resp.text[:500]
    return resp.status_code, body


def main() -> None:
    status, users = call("POST", "/laundry/v5/users")
    print(f"users: HTTP {status}")
    if isinstance(users, dict):
        selected = (users.get("selected_device") or {})
        appliance_id = selected.get("appliance_id")
        com_id = selected.get("com_id") or selected.get("model")
        print(f"  appliance_id: {appliance_id}")
        print(f"  com_id/model: {com_id}")
        print(f"  selected_device keys: {list(selected.keys())}")
        print(f"  users top keys: {list(users.keys())}")
    else:
        print(f"  body: {users}")
        appliance_id = os.environ.get("APPLIANCE_ID")

    com_id = os.environ.get("COM_ID", "NA-VX9800")
    if isinstance(users, dict):
        selected_com = (users.get("selected_device") or {}).get("com_id") or (
            users.get("selected_device") or {}
        ).get("model")
        if selected_com:
            com_id = selected_com
    status, info = call("GET", "/laundry/v5/device/info", params={"com_id": com_id})
    print(f"device/info ({com_id}): HTTP {status}")
    if isinstance(info, dict):
        devices = info.get("devices") or []
        print(f"  devices returned: {len(devices)}")
        for i, dev in enumerate(devices[:3]):
            cmds = dev.get("supported_cmds") or []
            print(
                f"  device[{i}] com_id={dev.get('com_id')} "
                f"product={dev.get('product_number')} supported_cmds={len(cmds)}"
            )
            if cmds:
                get_ids = cmds[0].get("get") or []
                print(f"    get properties: {len(get_ids)}")

    if not appliance_id:
        print("No appliance_id; cannot query status")
        return

    extra = {
        "X-ApplianceId": appliance_id,
        "X-VerifyAppliance": "true",
    }
    paths = [
        "/laundry/v5/device/status/",
        "/laundry/v5/device/status",
    ]
    for path in paths:
        for cached in ("false", None):
            label = f"{path} ({'live' if cached == 'false' else 'cached'})"
            h = {**HEADERS, **extra}
            if cached:
                h["X-Cached"] = cached
            resp = requests.get(f"{BASE}{path}", headers=h, timeout=30)
            print(f"status {label}: HTTP {resp.status_code}")
            print(f"  body: {resp.text[:400]}")


if __name__ == "__main__":
    main()
