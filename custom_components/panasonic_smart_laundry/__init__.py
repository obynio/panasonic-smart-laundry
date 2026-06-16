"""The Panasonic Smart Laundry integration."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_point_in_time

from .api import PanasonicSmartLaundryApi
from .const import DOMAIN, TOKEN_REFRESH_BUFFER
from .coordinator import PanasonicSmartLaundryCoordinator

logger = logging.getLogger(__name__)

platforms = [Platform.SENSOR, Platform.BINARY_SENSOR]


def _refresh_before_expiry(token_expires_at: float) -> datetime:
    """Return when to refresh, based on the stored token expiry."""
    return datetime.fromtimestamp(
        token_expires_at - TOKEN_REFRESH_BUFFER,
        tz=timezone.utc,
    )


def _tokens_changed(api: PanasonicSmartLaundryApi, entry: ConfigEntry) -> bool:
    return (
        api.access_token != entry.data.get("access_token")
        or api.refresh_token != entry.data.get("refresh_token")
        or api.token_expires_at != entry.data.get("token_expires_at")
    )


async def _persist_tokens(hass: HomeAssistant, entry: ConfigEntry, api: PanasonicSmartLaundryApi) -> None:
    if not _tokens_changed(api, entry):
        return
    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            "access_token": api.access_token,
            "refresh_token": api.refresh_token,
            "token_expires_at": api.token_expires_at,
        },
    )
    logger.debug("Persisted refreshed OAuth tokens")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Panasonic Smart Laundry from a config entry."""
    session = async_get_clientsession(hass)
    refresh_unsub: Callable[[], None] | None = None

    def _cancel_token_refresh() -> None:
        nonlocal refresh_unsub
        if refresh_unsub is not None:
            refresh_unsub()
            refresh_unsub = None

    def _schedule_token_refresh() -> None:
        nonlocal refresh_unsub
        _cancel_token_refresh()
        if not api.refresh_token or api.token_expires_at is None:
            return

        refresh_at = _refresh_before_expiry(api.token_expires_at)
        expires_at = datetime.fromtimestamp(api.token_expires_at, tz=timezone.utc)
        now = datetime.now(timezone.utc)
        if refresh_at <= now:
            logger.debug(
                "Access token expires at %s; refreshing now",
                expires_at.isoformat(),
            )
            hass.async_create_task(_refresh_tokens(now))
            return

        refresh_unsub = async_track_point_in_time(hass, _refresh_tokens, refresh_at)
        logger.debug(
            "Access token expires at %s; next refresh scheduled for %s",
            expires_at.isoformat(),
            refresh_at.isoformat(),
        )

    async def _refresh_tokens(_now: datetime) -> None:
        try:
            await api.refresh_access_token()
        except Exception:
            logger.warning("Scheduled token refresh failed", exc_info=True)
            _cancel_token_refresh()
            if api.token_expires_at is None:
                retry_at = datetime.now(timezone.utc) + timedelta(minutes=5)
            else:
                retry_at = _refresh_before_expiry(api.token_expires_at)
                if retry_at <= datetime.now(timezone.utc):
                    retry_at = datetime.now(timezone.utc) + timedelta(minutes=5)
            nonlocal refresh_unsub
            refresh_unsub = async_track_point_in_time(hass, _refresh_tokens, retry_at)
            logger.debug("Token refresh retry scheduled for %s", retry_at.isoformat())

    async def on_tokens_updated() -> None:
        await _persist_tokens(hass, entry, api)
        _schedule_token_refresh()

    api = PanasonicSmartLaundryApi(
        session,
        entry.data["username"],
        entry.data["password"],
        access_token=entry.data.get("access_token"),
        refresh_token=entry.data.get("refresh_token"),
        token_expires_at=entry.data.get("token_expires_at"),
        on_tokens_updated=on_tokens_updated,
    )

    if not entry.data.get("access_token"):
        await api.login()
    elif api.token_expires_at is None or time.time() >= api.token_expires_at - TOKEN_REFRESH_BUFFER:
        await api.refresh_access_token()

    await api.get_device_info(entry.data["com_id"])

    coordinator = PanasonicSmartLaundryCoordinator(hass, entry, api)
    coordinator._cancel_token_refresh = _cancel_token_refresh  # noqa: SLF001
    await coordinator.async_config_entry_first_refresh()

    _schedule_token_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, platforms):
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        if cancel := getattr(coordinator, "_cancel_token_refresh", None):
            cancel()
    return unload_ok
