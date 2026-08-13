"""Turn raw API status into values entities can display."""

from __future__ import annotations

from dataclasses import dataclass

from .const import OPERATION_KEYS, TRANSITION_KEYS

RemainingTimeValue = int | None

OPERATION = "0121"
TRANSITION = "00E2"

_WASH_OPS = frozenset({"01", "03", "05", "0F", "10"})
_WASH_TRANSITIONS = frozenset({"41", "42", "43", "E1"})
_DRY_OPS = frozenset({"06", "07", "18", "19"})
_NANOE_OPS = frozenset({"09", "0A", "0B"})
_NANOE_TRANSITIONS = frozenset({"E3"})
_WAITING_FOR_NANOE_OP = "0A"
_IDLE_OPS = frozenset({"00", "12", "EF"})
_IDLE_TRANSITIONS = frozenset({"00", "45", "51", "53", "54", "61", "EF"})
_FINISHED_TRANSITIONS = frozenset({"45", "51", "53", "54", "EF"})


@dataclass
class LaundryDeviceData:
    """Normalized washing machine state."""

    raw: dict[str, str]
    operation: str | None
    transition: str | None
    remaining_minutes: RemainingTimeValue
    wash_remaining_minutes: RemainingTimeValue
    dry_remaining_minutes: RemainingTimeValue
    progress_percent: int | None = None


def parse_remaining_time(raw: str | None) -> RemainingTimeValue:
    """Parse ECHONET time payloads into minutes, or unknown."""
    if not raw:
        return None
    cleaned = raw.strip().upper()
    if cleaned in {"FFFF", "FF", "0000", "00"}:
        return 0

    if len(cleaned) == 4 and all(c in "0123456789ABCDEF" for c in cleaned):
        hours = int(cleaned[0:2], 16)
        minutes = int(cleaned[2:4], 16)
        if hours == 0xFF and minutes == 0xFF:
            return 0
        if minutes <= 59:
            return hours * 60 + minutes

    if len(cleaned) == 2:
        value = int(cleaned, 16)
        return 0 if value == 0xFF else value

    if cleaned.isdigit():
        return int(cleaned)
    return None


def _phase(raw: dict[str, str]) -> tuple[str, str]:
    return raw.get(OPERATION, ""), raw.get(TRANSITION, "")


def _remaining_when(raw: dict[str, str], prop_id: str, *, active: bool) -> RemainingTimeValue:
    return parse_remaining_time(raw.get(prop_id)) if active else 0


def _is_washing(operation: str, transition: str) -> bool:
    if operation in _NANOE_OPS or transition in _NANOE_TRANSITIONS:
        return False
    return (
        operation in _WASH_OPS
        or transition in _WASH_TRANSITIONS
        or (operation == "14" and transition == "E1")
    )


def _is_drying(operation: str, transition: str) -> bool:
    return operation in _DRY_OPS or transition == "52"


def _is_waiting_for_nanoe(operation: str) -> bool:
    return operation == _WAITING_FOR_NANOE_OP


def cycle_should_reset(data: LaundryDeviceData) -> bool:
    """Return whether in-cycle progress tracking should be cleared."""
    power = data.raw.get("0080")
    if power == "31":
        return True

    transition = data.raw.get(TRANSITION, "")
    if transition in _FINISHED_TRANSITIONS:
        return True

    operation, transition = _phase(data.raw)
    return operation in _IDLE_OPS and transition in _IDLE_TRANSITIONS


def _course_remaining_minutes(
    raw: dict[str, str], operation: str, transition: str
) -> RemainingTimeValue:
    """Pick the best remaining-time source for the current phase."""
    if _is_waiting_for_nanoe(operation):
        return 0

    total = parse_remaining_time(raw.get("00ED"))

    if _is_drying(operation, transition):
        dry = parse_remaining_time(raw.get("00DC"))
        if dry is not None and dry > 0:
            return dry

    if _is_washing(operation, transition):
        wash = parse_remaining_time(raw.get("00DB"))
        if total is not None and total > 0:
            return total
        if wash is not None and wash > 0:
            return wash

    return total


def build_device_data(raw: dict[str, str]) -> LaundryDeviceData:
    """Build normalized state from a status property map."""
    operation, transition = _phase(raw)
    wash_remaining_minutes = _remaining_when(
        raw, "00DB", active=_is_washing(operation, transition)
    )
    dry_remaining_minutes = _remaining_when(
        raw, "00DC", active=_is_drying(operation, transition)
    )
    return LaundryDeviceData(
        raw=raw,
        operation=OPERATION_KEYS.get(operation, operation),
        transition=TRANSITION_KEYS.get(transition, transition),
        remaining_minutes=_course_remaining_minutes(raw, operation, transition),
        wash_remaining_minutes=wash_remaining_minutes,
        dry_remaining_minutes=dry_remaining_minutes,
    )


def is_device_running(data: LaundryDeviceData) -> bool:
    """True when the machine is in an active cycle."""
    if not data.raw:
        return False

    power = data.raw.get("0080")
    if power == "31":
        return False

    if any(
        minutes is not None and minutes > 0
        for minutes in (
            data.remaining_minutes,
            data.wash_remaining_minutes,
            data.dry_remaining_minutes,
        )
    ):
        return True

    operation, transition = _phase(data.raw)
    if operation and operation not in _IDLE_OPS:
        return True
    return bool(transition and transition not in _IDLE_TRANSITIONS)


def compute_cycle_progress(
    data: LaundryDeviceData,
    *,
    running: bool,
    elapsed_minutes: float | None,
) -> int | None:
    """Estimate course progress from elapsed time and remaining time."""
    if not running:
        transition = data.raw.get(TRANSITION, "")
        if transition in _FINISHED_TRANSITIONS:
            return 100
        return 0

    operation, _ = _phase(data.raw)
    if _is_waiting_for_nanoe(operation):
        return 100

    remaining = data.remaining_minutes
    if remaining is None:
        return None
    if remaining <= 0:
        return 100
    if elapsed_minutes is None or elapsed_minutes <= 0:
        return 0

    progress = round(100 * elapsed_minutes / (elapsed_minutes + remaining))
    return max(0, min(100, progress))
