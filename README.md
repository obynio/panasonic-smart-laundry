# Panasonic Smart Laundry for Home Assistant

Custom integration for Panasonic Japan **Smart Laundry** (`com.panasonic.SmartLaundry`) washing machines, including the **NA-VX9800L-W**.

It uses the same CLUB Panasonic OAuth flow and cloud API as the official Android app.

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
   - Repository: `obynio/panasonic`
   - Category: Integration
2. Install **Panasonic Smart Laundry**
3. Restart Home Assistant

### Manual

Copy the folder `custom_components/panasonic_smart_laundry` into your Home Assistant `config/custom_components/` directory and restart Home Assistant.

## Configuration

1. Go to **Settings → Devices & services → Add integration**
2. Search for **Panasonic Smart Laundry**
3. Sign in with the same CLUB Panasonic account as the mobile app
4. Defaults are pre-filled for the NA-VX9800:
   - Product number: `NA-VX9800L-W`
   - Communication ID: `NA-VX9800`

The integration discovers your selected appliance from `POST /laundry/v5/users`.

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
