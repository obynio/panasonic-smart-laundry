"""Display labels for ECHONET property codes.

Each model has one file: labels/{COM_ID}.json

    {
      "00D0": {
        "21": {"ja": "おまかせ", "en": "Omakase"}
      }
    }

At runtime:
  - Japanese: live device/info from the API, then the bundled file
  - English: bundled file only
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .api import PanasonicSmartLaundryApi

logger = logging.getLogger(__name__)

LABELS_DIR = Path(__file__).parent / "labels"
COURSE_PROPERTIES = ("00D0", "00FA", "01E6")
TRANSITION = "00E2"
NO_COURSE_TRANSITIONS = frozenset({"00", "61"})
EMPTY_LABELS = {"ja": "なし", "en": "None"}


@lru_cache(maxsize=64)
def _load_model_labels(com_id: str) -> dict[str, dict[str, dict[str, str]]]:
    path = LABELS_DIR / f"{com_id}.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("Could not load labels from %s", path)
        return {}


def _bundled(com_id: str, prop_id: str, value: str, *, japanese: bool) -> str | None:
    entry = _load_model_labels(com_id).get(prop_id, {}).get(value)
    if not entry:
        if value == "00":
            return EMPTY_LABELS["ja" if japanese else "en"]
        return None
    text = entry.get("ja" if japanese else "en")
    return text or None


def has_bundled_property(com_id: str, prop_id: str) -> bool:
    """Return whether bundled labels define values for a property."""
    return prop_id.upper() in _load_model_labels(com_id)


def get_display_label(
    api: PanasonicSmartLaundryApi,
    com_id: str,
    prop_id: str,
    value: str | None,
    *,
    japanese: bool,
) -> str | None:
    """Return the label to show in the UI for one property value."""
    if not value:
        return None

    prop_id = prop_id.upper()
    if japanese:
        return api.get_label(prop_id, value) or _bundled(
            com_id, prop_id, value, japanese=True
        )

    return _bundled(com_id, prop_id, value, japanese=False)


def get_course_label(
    api: PanasonicSmartLaundryApi,
    com_id: str,
    raw: dict[str, str],
    *,
    japanese: bool,
) -> str | None:
    """Return a course label from the main or alternate course properties."""
    for prop_id in COURSE_PROPERTIES:
        value = raw.get(prop_id)
        if not value:
            continue
        label = get_display_label(api, com_id, prop_id, value, japanese=japanese)
        if label:
            return label
    return None


def resolve_course_label(
    api: PanasonicSmartLaundryApi,
    com_id: str,
    raw: dict[str, str],
    *,
    japanese: bool,
) -> str | None:
    """Return the course label, or None/なし when no course is running."""
    if raw.get(TRANSITION, "") in NO_COURSE_TRANSITIONS:
        return EMPTY_LABELS["ja" if japanese else "en"]
    return get_course_label(api, com_id, raw, japanese=japanese)
