"""Tests for API parsing and state normalization."""

from __future__ import annotations

import pytest

from tests.conftest import (
    Api,
    build_device_data,
    is_device_running,
    normalize_id,
    normalize_value,
    parse_remaining_time,
    parse_status,
)

# Values from tests/fixtures/status_econavi.json (Econavi idle, power OFF).
ECONAVI_STATUS = {
    "0121": "1C",  # Econavi indicator on
    "0080": "31",  # Power OFF
    "00E2": "00",
    "00D0": "81",  # Individual wash course
    "00B0": "42",  # Door closed
    "0100": "02",  # Remote control disabled
    "00F4": "01",  # Standard drying
    "0136": "00",
    "0137": "00",
    "00ED": "FFFF",
    "00DB": "FFFF",
    "00DC": "FFFF",
    "0124": "0002",
}


def test_normalize_property_codes():
    assert normalize_id("121") == "0121"
    assert normalize_id("0xED") == "00ED"
    assert normalize_value("1C") == "1C"
    assert normalize_value("0x42") == "42"


def test_parse_econavi_status_fixture(parsed):
    for prop_id, value in ECONAVI_STATUS.items():
        assert parsed[prop_id] == value


def test_parse_status_ignores_empty_values():
    parsed = parse_status(
        {
            "status": [
                {"id": "0121", "params": [{"value": ""}]},
                {"id": "00ED", "params": [{"state": "0130"}]},
            ]
        }
    )
    assert "0121" not in parsed
    assert parsed["00ED"] == "0130"


def test_parse_status_falls_back_to_cmd_infos():
    parsed = parse_status(
        {
            "status": [],
            "cmd_infos": [{"id": "0121", "params": [{"value": "01"}]}],
        }
    )
    assert parsed["0121"] == "01"


def test_parse_status_skips_course_metadata():
    parsed = parse_status(
        {
            "status": [],
            "cmd_infos": [
                {
                    "id": "00D0",
                    "params": [
                        {
                            "wash_dry_course_code": "61",
                            "wash_dry_course_name": "おまかせ",
                        }
                    ],
                }
            ],
        }
    )
    assert "00D0" not in parsed


def test_labels_from_device_info(device):
    client = Api(session=None, username="user@example.com", password="secret")  # type: ignore[arg-type]
    client._device_info = device

    assert client.get_label("0121", "1C") == "エコナビ点灯中"
    assert client.get_label("00D0", "81") == "個別洗濯"
    assert client.get_label("00B0", "42") == "閉"
    assert client.get_label("0080", "31") == "OFF"


def test_label_requires_device_info():
    client = Api(session=None, username="user@example.com", password="secret")  # type: ignore[arg-type]
    assert client.get_label("0121", "1C") is None


@pytest.mark.parametrize(
    ("raw", "minutes"),
    [
        ("FFFF", 0),
        ("FF", 0),
        ("0000", 0),
        ("0002", 2),
        ("0130", 108),  # 1h48 in HH:MM hex
        ("25", 37),
        (None, None),
        ("", None),
    ],
)
def test_remaining_time_parser(raw, minutes):
    assert parse_remaining_time(raw) == minutes


def test_device_data_from_econavi_fixture(parsed):
    data = build_device_data(parsed)

    assert data.operation == "1C"
    assert data.transition == "00"
    assert data.remaining_minutes == 0
    assert data.wash_remaining_minutes == 0
    assert data.dry_remaining_minutes == 0
    assert is_device_running(data) is False


def test_device_data_with_numeric_times():
    data = build_device_data(
        {
            "0121": "01",
            "00E2": "41",
            "00ED": "0130",
            "00DB": "0025",
            "00DC": "0010",
        }
    )

    assert data.remaining_minutes == 108
    assert data.wash_remaining_minutes == 37
    assert data.dry_remaining_minutes == 0


def test_dry_remaining_time_during_drying():
    data = build_device_data(
        {
            "0121": "06",
            "00E2": "52",
            "00ED": "0130",
            "00DB": "0025",
            "00DC": "0010",
        }
    )

    assert data.wash_remaining_minutes == 0
    assert data.dry_remaining_minutes == 16


@pytest.mark.parametrize(
    ("operation", "transition"),
    [
        ("01", "41"),  # washing
        ("03", "42"),  # rinsing
        ("05", "43"),  # spinning
        ("01", "E1"),  # pre-wash
        ("00", "00"),  # idle
        ("00", "45"),  # finished wash only
        ("00", "61"),  # standby before start
        ("0B", "E3"),  # nanoe tub clean
        ("09", "00"),  # nanoe running
        ("0A", "00"),  # waiting for nanoe
    ],
)
def test_dry_remaining_time_zero_when_not_drying(operation, transition):
    """ECHONET may mirror wash time into 00DC outside of drying."""
    dry_raw = "0025"  # 37 minutes if parsed directly
    data = build_device_data(
        {
            "0121": operation,
            "00E2": transition,
            "00DC": dry_raw,
        }
    )

    assert parse_remaining_time(dry_raw) == 37
    assert data.dry_remaining_minutes == 0


@pytest.mark.parametrize(
    ("operation", "transition", "dry_raw", "expected_minutes"),
    [
        ("06", "52", "0010", 16),  # drying
        ("07", "52", "0025", 37),  # fluffing during dry phase
        ("06", "00", "0010", 16),  # drying operation alone
    ],
)
def test_dry_remaining_time_shown_when_drying(operation, transition, dry_raw, expected_minutes):
    data = build_device_data(
        {
            "0121": operation,
            "00E2": transition,
            "00DC": dry_raw,
        }
    )

    assert data.dry_remaining_minutes == expected_minutes


@pytest.mark.parametrize(
    ("operation", "transition"),
    [
        ("06", "52"),  # drying
        ("07", "52"),  # fluffing
        ("00", "00"),  # idle
        ("00", "45"),  # finished wash only
        ("00", "51"),  # finished dry
        ("00", "61"),  # standby before start
        ("0B", "E3"),  # nanoe tub clean
        ("09", "00"),  # nanoe running
        ("0A", "00"),  # waiting for nanoe
        ("00", "E3"),  # nanoe cycle
    ],
)
def test_wash_remaining_time_zero_when_not_washing(operation, transition):
    """ECHONET may mirror total time into 00DB outside of washing."""
    wash_raw = "0025"  # 37 minutes if parsed directly
    data = build_device_data(
        {
            "0121": operation,
            "00E2": transition,
            "00DB": wash_raw,
        }
    )

    assert parse_remaining_time(wash_raw) == 37
    assert data.wash_remaining_minutes == 0


@pytest.mark.parametrize(
    ("operation", "transition", "wash_raw", "expected_minutes"),
    [
        ("01", "41", "0025", 37),  # washing
        ("03", "42", "0010", 16),  # rinsing
        ("05", "43", "000A", 10),  # spinning
        ("01", "E1", "0025", 37),  # pre-wash
        ("0F", "42", "0010", 16),  # corrective rinsing
        ("10", "41", "0005", 5),  # foam dissipation stirring
        ("14", "E1", "0025", 37),  # pre-wash operation
        ("0C", "43", "0010", 16),  # paused during spin
    ],
)
def test_wash_remaining_time_shown_when_washing(
    operation, transition, wash_raw, expected_minutes
):
    data = build_device_data(
        {
            "0121": operation,
            "00E2": transition,
            "00DB": wash_raw,
        }
    )

    assert data.wash_remaining_minutes == expected_minutes


@pytest.mark.parametrize(
    ("properties", "running"),
    [
        ({"0080": "30", "0121": "00", "00E2": "00"}, True),
        ({"0080": "30", "0121": "01", "00E2": "41"}, True),
        ({"0080": "30", "0121": "00", "00E2": "00", "00ED": "0005"}, True),
        ({"0080": "31", "0121": "01", "00E2": "41"}, False),
    ],
)
def test_running_state(properties, running):
    assert is_device_running(build_device_data(properties)) is running
