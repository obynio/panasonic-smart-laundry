"""Panasonic Smart Laundry cloud API client."""

from __future__ import annotations

import base64
import hashlib
import html
import json
import logging
import re
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp

from .const import (
    API_BASE_URL,
    AUTH0_CLIENT,
    AUTH_URL,
    CLIENT_ID,
    DEFAULT_COM_ID,
    OAUTH_AUDIENCE,
    OAUTH_SCOPE,
    REDIRECT_URI,
    TOKEN_REFRESH_BUFFER,
)

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

AUTH_CODE_RE = re.compile(r"[?&]code=([^&]+)")
REDIRECT_STATUSES = {301, 302, 303, 307, 308}


def _absolute_auth_url(location: str, base: str = AUTH_URL) -> str:
    """Resolve Auth0 relative redirects against the login provider base URL."""
    if location.startswith(("http://", "https://", "auth0://")):
        return location
    if location.startswith("/"):
        return f"{base}{location}"
    return f"{base}/{location}"


def _extract_auth_code(location: str | None) -> str | None:
    """Extract an OAuth authorization code from a redirect URL."""
    if not location:
        return None
    match = AUTH_CODE_RE.search(location)
    return match.group(1) if match else None


def _normalize_prop_id(prop_id: str | int) -> str:
    """Normalize ECHONET property IDs to 4-digit uppercase hex."""
    text = str(prop_id).strip().upper().removeprefix("0X")
    if all(c in "0123456789ABCDEF" for c in text):
        return text.zfill(4)
    return text


def _normalize_prop_value(value: Any) -> str:
    """Normalize single-byte ECHONET property values."""
    if value is None:
        return ""
    text = str(value).strip().upper().removeprefix("0X")
    if text and all(c in "0123456789ABCDEF" for c in text) and len(text) <= 2:
        return text.zfill(2)
    return text


class PanasonicAuthError(Exception):
    """Authentication failed."""


class PanasonicApiError(Exception):
    """API request failed."""


class PanasonicSmartLaundryApi:
    """Async client for the Panasonic Smart Laundry cloud API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        *,
        access_token: str | None = None,
        refresh_token: str | None = None,
        token_expires_at: float | None = None,
        on_tokens_updated: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._token_expires_at = token_expires_at
        self._on_tokens_updated = on_tokens_updated
        self._device_info: dict[str, Any] | None = None

    @property
    def access_token(self) -> str | None:
        """Return the current access token."""
        return self._access_token

    @property
    def refresh_token(self) -> str | None:
        """Return the current refresh token."""
        return self._refresh_token

    @property
    def token_expires_at(self) -> float | None:
        """Return the access token expiry timestamp."""
        return self._token_expires_at

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(JST).strftime("%Y%m%d%H%M%S%z")

    def _auth_headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        if not self._access_token:
            msg = "Not authenticated"
            raise PanasonicAuthError(msg)
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json",
            "X-Timestamp": self._timestamp(),
        }
        if extra:
            headers.update(extra)
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> Any:
        await self.ensure_token()
        url = f"{API_BASE_URL}{path}"
        for attempt in range(2):
            async with self._session.request(
                method,
                url,
                headers=self._auth_headers(extra_headers),
                json=json_body,
                params=params,
            ) as response:
                text = await response.text()
                if response.status == 401 and attempt == 0:
                    await self.refresh_access_token()
                    continue
                if response.status == 401:
                    raise PanasonicAuthError("Unauthorized")
                if response.status >= 400:
                    raise PanasonicApiError(
                        f"{method} {path} failed with {response.status}: {text[:300]}"
                    )
                if not text:
                    return {}
                return json.loads(text)
        raise PanasonicAuthError("Unauthorized")

    async def _follow_auth_redirects(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str] | None = None,
        data: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
        max_redirects: int = 10,
    ) -> tuple[str | None, str | None]:
        """Follow HTTP redirects manually and stop on auth0:// callback URLs."""
        current_url = url
        request_params = params
        request_data = data
        request_json = json_body

        for _ in range(max_redirects):
            async with self._session.request(
                method,
                current_url,
                params=request_params,
                data=request_data,
                json=request_json,
                allow_redirects=False,
            ) as response:
                location = response.headers.get("Location")
                auth_code = _extract_auth_code(location)
                if auth_code:
                    return None, auth_code

                if response.status in REDIRECT_STATUSES and location:
                    if location.startswith("auth0://"):
                        auth_code = _extract_auth_code(location)
                        if auth_code:
                            return None, auth_code
                        raise PanasonicAuthError("Invalid OAuth redirect")

                    current_url = _absolute_auth_url(location, str(response.url.origin()))
                    method = "GET"
                    request_params = None
                    request_data = None
                    request_json = None
                    continue

                if response.status >= 400:
                    text = await response.text()
                    raise PanasonicAuthError(
                        f"Auth request failed with {response.status}: {text[:200]}"
                    )

                return await response.text(), None

        raise PanasonicAuthError("Too many OAuth redirects")

    async def login(self) -> dict[str, Any]:
        """Perform OAuth login and store tokens."""
        code_verifier = re.sub(
            r"[^a-zA-Z0-9]+",
            "",
            base64.urlsafe_b64encode(os_urandom(40)).decode("utf-8"),
        )
        code_challenge = (
            base64.urlsafe_b64encode(
                hashlib.sha256(code_verifier.encode()).digest()
            )
            .decode("utf-8")
            .replace("=", "")
        )
        nonce = base64.urlsafe_b64encode(os_urandom(40)).decode("utf-8")
        state = base64.urlsafe_b64encode(os_urandom(40)).decode("utf-8")

        authorize_params = {
            "response_type": "code",
            "client_id": CLIENT_ID,
            "tenant": "pdpauth-a1",
            "redirect_uri": REDIRECT_URI,
            "scope": OAUTH_SCOPE,
            "audience": OAUTH_AUDIENCE,
            "connection": "CLUBPanasonic-Authentication",
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "_intstate": "deprecated",
        }

        page, auth_code = await self._follow_auth_redirects(
            "GET",
            f"{AUTH_URL}/authorize",
            params=authorize_params,
        )
        if auth_code:
            return await self._exchange_code(auth_code, code_verifier)
        if not page:
            raise PanasonicAuthError("Could not parse login page")

        config_match = re.search(r"window\.atob\('([^']+)'\)", page)
        if not config_match:
            raise PanasonicAuthError("Could not parse login page")
        config = json.loads(base64.b64decode(config_match.group(1)).decode("utf-8"))
        csrf_token = config["extraParams"]["_csrf"]

        async with self._session.post(
            f"{AUTH_URL}/usernamepassword/login",
            json={
                "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "tenant": "pdpauth-a1",
                "response_type": "code",
                "scope": OAUTH_SCOPE,
                "audience": OAUTH_AUDIENCE,
                "_csrf": csrf_token,
                "state": config["extraParams"]["state"],
                "_intstate": "deprecated",
                "nonce": config["extraParams"]["nonce"],
                "username": self._username,
                "password": self._password,
                "connection": "CLUBPanasonic-Authentication",
                "captcha": None,
            },
        ) as response:
            login_page = await response.text()

        wa_match = re.search(r'name="wa"[^>]*value="([^"]+)"', login_page)
        wresult_match = re.search(r'name="wresult"[^>]*value="([^"]+)"', login_page)
        wctx_match = re.search(r'name="wctx"[^>]*value="([^"]+)"', login_page)
        if not wa_match or not wresult_match or not wctx_match:
            raise PanasonicAuthError("Login failed")

        async with self._session.post(
            f"{AUTH_URL}/login/callback",
            data={
                "wa": wa_match.group(1),
                "wresult": wresult_match.group(1),
                "wctx": html.unescape(wctx_match.group(1)),
            },
            allow_redirects=False,
        ) as response:
            location = response.headers.get("Location")
            if not location:
                raise PanasonicAuthError("Missing callback redirect")

        _, auth_code = await self._follow_auth_redirects(
            "GET",
            _absolute_auth_url(location),
        )
        if not auth_code:
            raise PanasonicAuthError("Missing authorization code")

        return await self._exchange_code(auth_code, code_verifier)

    async def refresh_access_token(self) -> dict[str, Any]:
        """Refresh the access token."""
        if not self._refresh_token:
            return await self.login()
        data = {
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "refresh_token": self._refresh_token,
        }
        async with self._session.post(
            f"{AUTH_URL}/oauth/token",
            json=data,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Auth0-Client": AUTH0_CLIENT,
                "User-Agent": "okhttp/4.12.0",
            },
        ) as response:
            payload = await response.json(content_type=None)
            if response.status >= 400:
                logger.debug("Refresh failed, falling back to login: %s", payload)
                return await self.login()
        return await self._apply_token_response(payload)

    async def ensure_token(self) -> None:
        """Ensure a valid access token is available."""
        if self._access_token and self._token_expires_at:
            if time.time() < self._token_expires_at - TOKEN_REFRESH_BUFFER:
                return
        if self._refresh_token:
            await self.refresh_access_token()
            return
        await self.login()

    async def _exchange_code(self, auth_code: str, code_verifier: str) -> dict[str, Any]:
        async with self._session.post(
            f"{AUTH_URL}/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "code": auth_code,
                "code_verifier": code_verifier,
            },
        ) as response:
            payload = await response.json(content_type=None)
            if response.status >= 400:
                raise PanasonicAuthError(str(payload))
        return await self._apply_token_response(payload)

    async def _apply_token_response(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self._store_token_payload(payload):
            await self._notify_tokens_updated()
        return payload

    async def _notify_tokens_updated(self) -> None:
        if self._on_tokens_updated is not None:
            await self._on_tokens_updated()

    def _store_token_payload(self, payload: dict[str, Any]) -> bool:
        access_token = payload["access_token"]
        refresh_token = payload.get("refresh_token", self._refresh_token)
        expires_in = payload.get("expires_in")
        token_expires_at = (
            time.time() + int(expires_in) if expires_in is not None else self._token_expires_at
        )
        changed = (
            access_token != self._access_token
            or refresh_token != self._refresh_token
            or token_expires_at != self._token_expires_at
        )
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._token_expires_at = token_expires_at
        return changed

    async def get_user_profile(self) -> dict[str, Any]:
        """Return user profile including selected appliance."""
        return await self._request("POST", "/laundry/v5/users")

    async def get_device_info(self, com_id: str = DEFAULT_COM_ID) -> dict[str, Any]:
        """Return static device capability metadata."""
        data = await self._request(
            "GET",
            "/laundry/v5/device/info",
            params={"com_id": com_id},
        )
        devices = data.get("devices") or []
        if not devices:
            raise PanasonicApiError("No device info returned")
        self._device_info = devices[0]
        return self._device_info

    async def get_status(self, *, appliance_id: str) -> dict[str, str]:
        """Fetch live ECHONET property values from the cloud."""
        data = await self._request(
            "GET",
            "/laundry/v5/device/status/",
            extra_headers={
                "X-ApplianceId": appliance_id,
                "X-Cached": "false",
                "X-VerifyAppliance": "true",
            },
        )
        return self._parse_status_response(data)

    def get_label(self, prop_id: str, value: str | None) -> str | None:
        """Resolve a human-readable label from cached device info."""
        if not value or not self._device_info:
            return None
        supported_cmds = self._device_info.get("supported_cmds") or []
        if not supported_cmds:
            return None
        cmds = supported_cmds[0].get("cmds") or []
        normalized_prop = _normalize_prop_id(prop_id)
        normalized_value = _normalize_prop_value(value)
        for cmd in cmds:
            if _normalize_prop_id(cmd.get("id", "")) != normalized_prop:
                continue
            for param in cmd.get("params") or []:
                param_value = _normalize_prop_value(param.get("value"))
                raw_param_value = str(param.get("value", "")).strip().upper()
                if param_value != normalized_value and raw_param_value != str(value).strip().upper():
                    continue
                name = (param.get("name") or "").strip()
                if name:
                    return name
                top = (param.get("name_top") or "").strip()
                bottom = (param.get("name_bottom") or "").strip()
                if top and bottom:
                    return f"{top}{bottom}"
                if top or bottom:
                    return top or bottom
        return None

    @staticmethod
    def _parse_status_response(data: dict[str, Any]) -> dict[str, str]:
        """Parse status payloads from the DeviceStatusResponse shape."""
        result: dict[str, str] = {}

        for item in data.get("status") or []:
            prop_id = item.get("id") or item.get("epc") or item.get("command_id")
            if not prop_id:
                continue
            params = item.get("params") or []
            if params:
                value = params[0].get("value")
                if value in (None, ""):
                    value = params[0].get("state")
            else:
                value = item.get("value") or item.get("state")
            if value is not None and value != "":
                result[_normalize_prop_id(prop_id)] = _normalize_prop_value(value)

        cmd_infos = data.get("cmd_infos") or data.get("cmds") or []
        for cmd in cmd_infos:
            prop_id = cmd.get("id")
            if not prop_id or _normalize_prop_id(prop_id) in result:
                continue
            params = cmd.get("params") or []
            if not params:
                if "value" in cmd:
                    result[_normalize_prop_id(prop_id)] = _normalize_prop_value(cmd["value"])
                continue
            if any(
                "wash_dry_course_code" in param or "wash_dry_course_name" in param
                for param in params
            ):
                continue
            value = params[0].get("value")
            if value is not None and value != "":
                result[_normalize_prop_id(prop_id)] = _normalize_prop_value(value)

        properties = data.get("properties") or data.get("property") or []
        for prop in properties:
            prop_id = prop.get("id") or prop.get("epc")
            value = prop.get("value") or prop.get("edt")
            if prop_id and value is not None:
                result[_normalize_prop_id(prop_id)] = _normalize_prop_value(value)

        return result


def os_urandom(size: int) -> bytes:
    """Small helper so login code stays easy to test."""
    import os

    return os.urandom(size)
