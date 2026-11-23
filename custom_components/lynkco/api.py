"""API client for Lynk & Co vehicles."""

import asyncio
import hashlib
import json
import logging
import re
import time
import urllib.parse
import uuid

import aiohttp
import pkce

from .const import (
    API_BASE,
    CLIENT_ID,
    COMMAND_BASE,
    IAM_BASE,
    LOGIN_B2C_URL,
    LOVE_BASE,
    REDIRECT_URI,
    SCOPE,
    SIGNATURE_BASE_URLS,
    SIGNATURE_VERSION,
    TENANT,
)

_LOGGER = logging.getLogger(__name__)

_MAX_DIAGNOSTIC_BODY = 1500
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)
SESSION_RECLAIM_INTERVAL = 60  # At most one automatic session claim per minute.


class LynkCoAuthError(Exception):
    """Refresh token permanently rejected: ask Home Assistant to reauthenticate."""


class LynkCoTransientError(Exception):
    """Temporary token endpoint or network failure; do not ask for a new login."""



def _compute_signature(secret: str, nonce: str, path: str) -> str:
    return hashlib.sha256((secret + nonce + path).encode("utf-8")).hexdigest()


def _extract_path(url: str) -> str:
    for base in SIGNATURE_BASE_URLS:
        if url.startswith(base):
            relative = url[len(base):]
            return "/" + relative.lstrip("/")
    parsed = urllib.parse.urlparse(url)
    return parsed.path


def _safe_path(url: str) -> str:
    """Return a log-safe API path with the VIN removed."""
    path = _extract_path(url)
    path = re.sub(r"/vehicle/[^/]+", "/vehicle/<vin>", path)
    return path


def _sanitize_diagnostic(value: object) -> str:
    """Return a short log-safe representation of a backend response."""
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError):
            text = repr(value)

    # Never leak bearer/JWT material if a backend unexpectedly echoes it.
    text = re.sub(
        r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
        "<jwt-redacted>",
        text,
    )
    text = re.sub(
        r'(?i)("?(?:access_token|refresh_token|authorization)"?\s*[:=]\s*")([^"]+)(")',
        r"\1<redacted>\3",
        text,
    )
    if len(text) > _MAX_DIAGNOSTIC_BODY:
        return text[:_MAX_DIAGNOSTIC_BODY] + "...<truncated>"
    return text


def _decode_jwt_claims(token: str) -> dict:
    import base64
    payload = token.split(".")[1]
    payload += "=" * (4 - len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


class LynkCoAPI:
    """Handles communication with the Lynk & Co API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        access_token: str,
        refresh_token: str,
        device_id: str,
        on_token_refresh: callable | None = None,
    ) -> None:
        self._session = session
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._device_id = device_id
        self._on_token_refresh = on_token_refresh
        self._refresh_lock = asyncio.Lock()
        # A 403 can be session takeover only on a previously successful endpoint.
        self._working_paths: set[str] = set()
        self._last_reclaim: float | None = None
        self._claims: dict = {}
        self._update_claims()

    def _update_claims(self) -> None:
        try:
            self._claims = _decode_jwt_claims(self._access_token)
        except Exception:
            _LOGGER.exception("Failed to decode JWT claims")
            self._claims = {}

    @property
    def customer_number(self) -> str:
        return self._claims.get("customerNumber", "")

    @property
    def snowflake_id(self) -> str:
        return self._claims.get("snowflakeId", "")

    @property
    def user_email(self) -> str:
        return self._claims.get("email", "")

    @property
    def access_token(self) -> str:
        return self._access_token

    @property
    def refresh_token(self) -> str:
        return self._refresh_token

    @property
    def device_id(self) -> str:
        return self._device_id

    def _build_headers(self, url: str) -> dict:
        nonce = str(uuid.uuid4())
        path = _extract_path(url)
        sig = _compute_signature(self.snowflake_id, nonce, path)

        return {
            "Authorization": f"Bearer {self._access_token}",
            "X-Auth-Token": self._access_token,
            "X-DeviceId": self._device_id,
            "X-CustomerNumber": self.customer_number,
            "X-CustomerId": self.snowflake_id,
            "User-Agent": "Android",
            "api-version": "1",
            "X-NONCE": nonce,
            "X-SIGNATURE-VERSION": SIGNATURE_VERSION,
            "X-SIGNATURE": sig,
            "X-App-Name": "Lynk&Co",
            "X-App-Version": "2.55.0",
            "X-App-Build-Number": "8284",
            "X-Device-OS-Version": "14",
            "X-Device-Model": "Pixel 8",
            "X-Device-Language": "en",
            "Content-Type": "application/json",
        }

    async def _response_data(self, resp: aiohttp.ClientResponse) -> dict:
        """Decode a JSON response while tolerating empty/non-JSON command replies."""
        if resp.content_length == 0:
            return {}
        try:
            data = await resp.json(content_type=None)
        except (aiohttp.ContentTypeError, json.JSONDecodeError, UnicodeDecodeError):
            text = await resp.text()
            return {"raw": text} if text else {}
        return data if isinstance(data, dict) else {"data": data}

    async def _log_http_error(
        self,
        method: str,
        url: str,
        resp: aiohttp.ClientResponse,
    ) -> None:
        """Log the useful backend error body without credentials or VIN."""
        try:
            body = await resp.text()
        except Exception:  # pragma: no cover - diagnostic best effort only
            body = "<unable to read response body>"
        _LOGGER.warning(
            "Lynk & Co API error: %s %s -> HTTP %s backend=%s",
            method,
            _safe_path(url),
            resp.status,
            _sanitize_diagnostic(body),
        )

    def _log_command_success(self, method: str, url: str, status: int, data: dict) -> None:
        """Log command acknowledgements so MY2022 behavior can be diagnosed."""
        if "/command/" not in _extract_path(url):
            return
        _LOGGER.info(
            "Lynk & Co command response: %s %s -> HTTP %s backend=%s",
            method,
            _safe_path(url),
            status,
            _sanitize_diagnostic(data),
        )

    async def _request(self, method: str, url: str, **kwargs) -> dict:
        """Retry a 401 after one token refresh, or a known 403 after session reclaim.

        An unknown 403 must never trigger a session reclaim: MY2022 endpoints
        may be unsupported, and claiming would eject the official phone app.
        """
        old_token = self._access_token
        path = _extract_path(url)
        kwargs.setdefault("timeout", REQUEST_TIMEOUT)
        headers = self._build_headers(url)

        async with self._session.request(method, url, headers=headers, **kwargs) as resp:
            taken = resp.status == 403 and path in self._working_paths
            if resp.status not in (401,) and not taken:
                return await self._read_response(method, url, resp)

        reclaimed = False
        if taken:
            reclaimed = await self._reclaim_session()
        else:
            # Multiple simultaneous 401s must not refresh the same token twice.
            async with self._refresh_lock:
                if old_token == self._access_token:
                    await self._refresh_tokens_locked()

        headers = self._build_headers(url)
        async with self._session.request(method, url, headers=headers, **kwargs) as retry:
            if retry.status == 401 and not taken:
                raise LynkCoAuthError("Still unauthorized after token refresh")
            if retry.status == 403 and reclaimed:
                # A 403 even after a successful reclaim is likely an unsupported
                # endpoint. Do not keep claiming the session on future polls.
                self._working_paths.discard(path)
            return await self._read_response(method, url, retry)

    async def _read_response(self, method: str, url: str, resp: aiohttp.ClientResponse) -> dict:
        """Preserve MY2022 diagnostics and status-aware readback."""
        if resp.status >= 400:
            await self._log_http_error(method, url, resp)
        resp.raise_for_status()
        self._working_paths.add(_extract_path(url))
        data = await self._response_data(resp)
        self._log_command_success(method, url, resp.status, data)
        return data

    async def refresh_tokens(self) -> bool:
        """Refresh once, serialized with all other refreshes and session claims."""
        async with self._refresh_lock:
            return await self._refresh_tokens_locked()

    async def _refresh_tokens_locked(self) -> bool:
        """Only call while holding _refresh_lock."""
        url = f"{LOGIN_B2C_URL}oauth2/v2.0/token"
        try:
            async with self._session.post(
                url,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "client_id": CLIENT_ID,
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                    "scope": SCOPE,
                    "redirect_uri": REDIRECT_URI,
                },
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                if resp.status != 200:
                    # Avoid including token-service response text, which might
                    # contain credentials or personally identifying information.
                    _LOGGER.warning("Lynk & Co token endpoint HTTP %d", resp.status)
                    if 400 <= resp.status < 500 and resp.status != 429:
                        raise LynkCoAuthError(
                            f"Refresh token rejected (HTTP {resp.status})"
                        )
                    raise LynkCoTransientError(
                        f"Token refresh temporarily unavailable (HTTP {resp.status})"
                    )
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise LynkCoTransientError(
                f"Token endpoint unreachable ({type(err).__name__})"
            ) from err
        except (ValueError, TypeError, KeyError) as err:
            raise LynkCoTransientError(
                f"Invalid token endpoint response ({type(err).__name__})"
            ) from err

        if not isinstance(data, dict) or not isinstance(data.get("access_token"), str):
            raise LynkCoTransientError("Token endpoint response lacks an access token")
        self._access_token = data["access_token"]
        self._refresh_token = data.get("refresh_token", self._refresh_token)
        self._update_claims()
        _LOGGER.debug("Lynk & Co tokens refreshed successfully")
        if self._on_token_refresh:
            self._on_token_refresh(self._access_token, self._refresh_token)
        return True

    async def _reclaim_session(self) -> bool:
        """Reclaim a confirmed taken session at most once per minute.

        This can log the official phone app out. Never call for a new/unknown
        or permanently forbidden MY2022 endpoint.
        """
        async with self._refresh_lock:
            if (
                self._last_reclaim is not None
                and time.monotonic() - self._last_reclaim < SESSION_RECLAIM_INTERVAL
            ):
                return False
            _LOGGER.warning(
                "Lynk & Co session may have moved to another device; "
                "trying a single session reclaim"
            )
            try:
                reclaimed = await self.validate_session()
            finally:
                # Also throttle failures/timeouts; avoid a storm of requests.
                self._last_reclaim = time.monotonic()
            if not reclaimed:
                _LOGGER.warning("Lynk & Co session reclaim not accepted")
            return reclaimed

    async def validate_session(self) -> bool:
        """Validate/claim this session, including a 'valid': false response."""
        url = f"{IAM_BASE}/validate-session"
        headers = self._build_headers(url)
        async with self._session.post(
            url,
            headers=headers,
            json={"deviceUuid": self._device_id, "isLogin": True},
            timeout=REQUEST_TIMEOUT,
        ) as resp:
            if resp.status != 200:
                _LOGGER.debug("Lynk & Co validate-session HTTP %d", resp.status)
                return False
            try:
                data = await resp.json(content_type=None)
            except (aiohttp.ClientError, ValueError):
                return True  # Older API variants may answer empty/non-JSON.
            return not (isinstance(data, dict) and data.get("valid") is False)

    async def get_vehicles(self) -> list[dict]:
        url = f"{LOVE_BASE}/list/vehicles"
        data = await self._request("GET", url)
        return data.get("listOfVehicles", [])

    async def get_vehicle_data(self, vin: str) -> dict:
        return await self._request("GET", f"{LOVE_BASE}/vehicle/{vin}/vehicle_data")

    async def get_location(self, vin: str) -> dict:
        return await self._request("GET", f"{LOVE_BASE}/vehicle/{vin}/location_state")

    async def get_charge_state(self, vin: str) -> dict:
        return await self._request("GET", f"{LOVE_BASE}/vehicle/{vin}/charge_state")

    async def get_climate_state(self, vin: str) -> dict:
        return await self._request("GET", f"{LOVE_BASE}/vehicle/{vin}/climate_state")

    async def get_doors_windows(self, vin: str) -> dict:
        return await self._request(
            "GET", f"{LOVE_BASE}/vehicle/{vin}/doors_windows_state"
        )

    async def get_vehicle_metadata(self, vin: str) -> dict:
        return await self._request("GET", f"{LOVE_BASE}/vehicle/{vin}/vehicle_metadata")

    async def get_fuel_state(self, vin: str) -> dict:
        return await self._request("GET", f"{LOVE_BASE}/vehicle/{vin}/fuel_state")

    async def lock_door(self, vin: str) -> dict:
        return await self._request(
            "POST", f"{COMMAND_BASE}/vehicle/{vin}/command/door_lock"
        )

    async def unlock_door(self, vin: str) -> dict:
        return await self._request(
            "POST", f"{COMMAND_BASE}/vehicle/{vin}/command/door_unlock"
        )

    async def request_location(self, vin: str) -> dict:
        """Ask the vehicle to report a fresh position.

        Declared but never called by the official app (v2.63.0); verified working
        against the live API. The car answers COMMAND_RECEIVED immediately and
        pushes a fresh position a few seconds later.
        """
        return await self._request(
            "POST", f"{COMMAND_BASE}/vehicle/{vin}/command/request_location"
        )

    async def flash_lights(self, vin: str) -> dict:
        return await self._request(
            "POST", f"{COMMAND_BASE}/vehicle/{vin}/command/flash_lights"
        )

    async def honk_horn(self, vin: str) -> dict:
        return await self._request(
            "POST", f"{COMMAND_BASE}/vehicle/{vin}/command/honk_horn"
        )

    async def open_sunroof(self, vin: str) -> dict:
        return await self._request(
            "POST", f"{COMMAND_BASE}/vehicle/{vin}/command/sun_roof_open"
        )

    async def close_sunroof(self, vin: str) -> dict:
        return await self._request(
            "POST", f"{COMMAND_BASE}/vehicle/{vin}/command/sun_roof_close"
        )

    async def set_charge_limit(self, vin: str, percent: int) -> dict:
        url = f"{COMMAND_BASE}/vehicle/{vin}/command/set_charge_limit"
        return await self._request("POST", url, params={"percent": percent})

    async def start_charging(self, vin: str) -> dict:
        return await self._request(
            "POST", f"{COMMAND_BASE}/vehicle/{vin}/command/charge_start"
        )

    async def stop_charging(self, vin: str) -> dict:
        return await self._request(
            "POST", f"{COMMAND_BASE}/vehicle/{vin}/command/charge_stop"
        )

    async def start_conditioning(self, vin: str, temp: int, level: int | None = None) -> dict:
        params = {"temp": temp}
        if level is not None:
            params["level"] = level
        return await self._request(
            "POST", f"{COMMAND_BASE}/vehicle/{vin}/command/auto_conditioning_start",
            params=params,
        )

    async def stop_conditioning(self, vin: str) -> dict:
        return await self._request(
            "POST", f"{COMMAND_BASE}/vehicle/{vin}/command/auto_conditioning_stop"
        )

    async def start_ventilate(self, vin: str) -> dict:
        return await self._request(
            "POST", f"{COMMAND_BASE}/vehicle/{vin}/command/ventilate_start"
        )

    async def stop_ventilate(self, vin: str) -> dict:
        return await self._request(
            "POST", f"{COMMAND_BASE}/vehicle/{vin}/command/ventilate_stop"
        )

    async def start_heaters(self, vin: str, heaters: list[str]) -> dict:
        return await self._request(
            "POST", f"{COMMAND_BASE}/vehicle/{vin}/command/start_heaters",
            json=heaters,
        )

    async def stop_heaters(self, vin: str, heaters: list[str]) -> dict:
        return await self._request(
            "POST", f"{COMMAND_BASE}/vehicle/{vin}/command/stop_heaters",
            json=heaters,
        )

    async def lock_glovebox(self, vin: str, password: str) -> dict:
        return await self._request(
            "POST", f"{COMMAND_BASE}/vehicle/{vin}/command/glovebox_set_password",
            json={"password": password},
        )

    async def unlock_glovebox(self, vin: str) -> dict:
        return await self._request(
            "POST", f"{COMMAND_BASE}/vehicle/{vin}/command/glovebox_unlock"
        )

    # --- Static helpers for the config flow auth ---

    @staticmethod
    def generate_auth_url() -> tuple[str, str, str]:
        """Generate B2C authorize URL. Returns (url, code_verifier, code_challenge)."""
        code_verifier, code_challenge = pkce.generate_pkce_pair()
        scope_encoded = urllib.parse.quote(SCOPE, safe="")
        redirect_encoded = urllib.parse.quote(REDIRECT_URI, safe="")
        url = (
            f"{LOGIN_B2C_URL}oauth2/v2.0/authorize"
            f"?response_type=code"
            f"&client_id={CLIENT_ID}"
            f"&scope={scope_encoded}"
            f"&code_challenge={code_challenge}"
            f"&code_challenge_method=S256"
            f"&redirect_uri={redirect_encoded}"
        )
        return url, code_verifier, code_challenge

    @staticmethod
    def extract_code_from_url(url: str) -> str | None:
        """Extract authorization code from msauth:// redirect URL."""
        if "code=" in url:
            if "?" in url:
                query = url.split("?", 1)[1]
            else:
                query = url
            return urllib.parse.parse_qs(query).get("code", [None])[0]
        return None

    @staticmethod
    async def exchange_code(
        session: aiohttp.ClientSession, code: str, code_verifier: str
    ) -> dict | None:
        """Exchange authorization code for tokens."""
        url = f"{LOGIN_B2C_URL}oauth2/v2.0/token"
        async with session.post(
            url,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "client_info": "1",
                "scope": SCOPE,
                "code": code,
                "grant_type": "authorization_code",
                "code_verifier": code_verifier,
                "redirect_uri": REDIRECT_URI,
                "client_id": CLIENT_ID,
            },
        ) as resp:
            if resp.status != 200:
                try:
                    body = await resp.text()
                except Exception:  # pragma: no cover - diagnostic best effort only
                    body = "<unable to read response body>"
                _LOGGER.error(
                    "Token exchange failed: HTTP %d backend=%s",
                    resp.status,
                    _sanitize_diagnostic(body),
                )
                return None
            return await resp.json()
