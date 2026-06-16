# Panasonic Smart Laundry for Home Assistant

Custom Home Assistant integration for Panasonic Japan connected washing machines.

## Reset history

```
action: recorder.purge_entities
data:
  entity_id:
    - sensor.na_vx9800_operation
    - sensor.na_vx9800_transition
    - sensor.na_vx9800_course
    - sensor.na_vx9800_remote_control
    - sensor.na_vx9800_detergent_supply
    - sensor.na_vx9800_softener_supply
    - sensor.na_vx9800_remaining_time
    - sensor.na_vx9800_dry_remaining_time
    - sensor.na_vx9800_wash_remaining_time
    - binary_sensor.na_vx9800_running
  keep_days: 0
```

## Features

- CLUB Panasonic login with token refresh
- Live status polling every 60 seconds
- Sensors for operation state, transition, course, and remaining times
- Binary sensor for running state

## Installation

### HACS (recommended)

1. Add this repository as a custom HACS integration:
   - Repository: `obynio/panasonic-smart-laundry`
   - Category: Integration
2. Install **Panasonic Smart Laundry**
3. Restart Home Assistant

### Manual

Copy the folder `custom_components/panasonic_smart_laundry` into your Home Assistant `config/custom_components/` directory and restart Home Assistant.

## Configuration

1. Go to **Settings → Devices & services → Add integration**
2. Search for **Panasonic Smart Laundry**
3. Sign in with your CLUB Panasonic account
4. Defaults are pre-filled for the NA-VX9800:
   - Product number: `NA-VX9800L-W`
   - Communication ID: `NA-VX9800`

The integration discovers your selected appliance from `POST /laundry/v5/users`.

## Supported machines

During setup, choose the **communication ID (COM ID)** that matches your machine. These models are supported:

### NA-F series

- `NA-F10AKE3`, `NA-F10AKE4`, `NA-F10AKE5`
- `NA-F8AKE3`, `NA-F8AKE4`, `NA-F8AKE5`
- `NA-F9AKE3`, `NA-F9AKE4`, `NA-F9AKE5`
- `NA-FA10K2`, `NA-FA10K3`, `NA-FA10K5`
- `NA-FA11K1`, `NA-FA11K2`, `NA-FA11K3`, `NA-FA11K5`
- `NA-FA12V1`, `NA-FA12V2`, `NA-FA12V3`, `NA-FA12V5`, `NA-FA12V6`
- `NA-FA8K2`, `NA-FA8K3`, `NA-FA8K5`
- `NA-FA9K2`, `NA-FA9K3`, `NA-FA9K5`
- `NA-FW10K1`, `NA-FW10K2`

### NA-LX series

- `NA-LX127A`, `NA-LX127B`, `NA-LX127C`, `NA-LX127D`, `NA-LX127E`
- `NA-LX129A`, `NA-LX129B`, `NA-LX129C`, `NA-LX129D`, `NA-LX129E`

### NA-SD series

- `NA-SD10UA`, `NA-SD10UB`

### NA-VG series

- `NA-VG1200`, `NA-VG1300`, `NA-VG1400`, `NA-VG1500`
- `NA-VG2200`, `NA-VG2300`, `NA-VG2400`, `NA-VG2500`
- `NA-VG2600`, `NA-VG2700`, `NA-VG2800`, `NA-VG2900`

### NA-VX series

- `NA-VX900A`, `NA-VX900B`, `NA-VX9800` (default), `NA-VX9900`

If your model is missing, open an issue with the COM ID shown on your machine label.

## Entities

| Entity | Description |
| --- | --- |
| `sensor.*_operation` | Detailed operation state (`0121`) |
| `sensor.*_transition` | High-level cycle state (`00E2`) |
| `sensor.*_course` | Selected course (`00D0`) |
| `sensor.*_remaining_time` | Total remaining time in minutes or N/A (`00ED`) |
| `sensor.*_wash_remaining_time` | Wash remaining time in minutes or N/A (`00DB`) |
| `sensor.*_dry_remaining_time` | Dry remaining time in minutes or N/A (`00DC`) |
| `sensor.*_remote_control` | Remote control: Enabled / Disabled (`0100`) |
| `sensor.*_detergent_supply` | Detergent tank: OK / Low / Unknown (`0136`) |
| `sensor.*_softener_supply` | Softener tank: OK / Low / Unknown (`0137`) |
| `binary_sensor.*_running` | Derived running state |

## API endpoints

| Action | Method | Path |
| --- | --- | --- |
| Live status | `GET` | `/laundry/v5/device/status/` |
| Device capabilities | `GET` | `/laundry/v5/device/info` |
| Course metadata | `POST` | `/laundry/v5/laundry/command` |
| User / selected device | `POST` | `/laundry/v5/users` |

All device calls require the `X-ApplianceId` header.

## Tests

Install dev dependencies with [uv](https://docs.astral.sh/uv/) and run pytest:

```bash
uv sync
uv run pytest tests/ -v
```

Tests use captured API fixtures under `tests/fixtures/` and do not require Home Assistant or live cloud credentials.

## Local auth test

You can still test OAuth from the repo root:

```bash
export PANASONIC_USERNAME="you@example.com"
export PANASONIC_PASSWORD="your-password"
uv run python auth.py
```

## Security

Store credentials only in Home Assistant's config entry storage. Do not commit tokens or passwords to git.
