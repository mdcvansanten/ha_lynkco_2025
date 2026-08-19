"""Remote command adapter for pre-2025 Lynk & Co 01 (CX11_A1).

The pre-2025 01 uses the older connectedcar.cloud remote-control backend.
This module deliberately exposes only the commands we have verified from the
legacy integration. Secrets, tokens and VINs are never logged.

The legacy AION endpoints currently present a certificate chain that Python's
standard trust validation cannot build inside Home Assistant. The historical
pre-2025 integration therefore used an aiohttp connector with ``ssl=False``.
To keep that compatibility workaround as narrow as possible, TLS verification
is disabled *per request* only for the three hard-coded Lynk & Co legacy HTTPS
endpoints below. The normal MY2025+ API and every other Home Assistant request
continue to use normal certificate validation.
"""

from __future__ import annotations

import logging

from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

IAM_VALIDATE_URL = (
    "https://iam-service-prod.westeurope.cloudapp.azure.com/validate-session"
)
DELEGATED_DRIVER_URL = (
    "https://delegated-driver-tls.aion.connectedcar.cloud/"
    "delegated-driver/api/delegateddriver/v1/vehicle/{vin}/drivers"
)
LEGACY_CLIMATE_URL = (
    "https://remote-vehicle-control-tls.aion.connectedcar.cloud/"
    "api/v1/rvc/vehicles/{vin}/remotecontrol/climate"
)

LEGACY_USER_AGENT = "LynkCo/3016 CFNetwork/1492.0.1 Darwin/23.3.0"
DEFAULT_CLIMATE_DURATION_MINUTES = 15
MAX_CLIMATE_DURATION_MINUTES = 20


class Legacy01Commands:
    """Execute confirmed legacy remote commands for a CX11_A1 vehicle."""

    def __init__(self, api) -> None:
        self._api = api
        self._session = api._session
        self._ccc_token: str | None = None
        self._user_id: str | None = None
        self._tls_warning_logged = False

    def _warn_legacy_tls(self) -> None:
        if self._tls_warning_logged:
            return
        self._tls_warning_logged = True
        _LOGGER.warning(
            "Legacy Lynk & Co 01 command backend requires a scoped TLS "
            "verification compatibility workaround; verification is disabled "
            "only for hard-coded legacy Lynk & Co command endpoints"
        )

    async def _get_ccc_token(self) -> str:
        if self._ccc_token:
            return self._ccc_token

        headers = {
            "user-agent": LEGACY_USER_AGENT,
            "accept": "application/json",
            "content-type": "application/json",
            "X-Auth-Token": self._api.access_token,
            "api-version": "1",
        }
        payload = {"deviceUuid": self._api.device_id, "isLogin": True}

        self._warn_legacy_tls()
        async with self._session.post(
            IAM_VALIDATE_URL, headers=headers, json=payload, ssl=False
        ) as response:
            if response.status != 200:
                _LOGGER.error(
                    "Legacy 01 authentication failed (HTTP %s)", response.status
                )
                raise HomeAssistantError(
                    f"Legacy Lynk & Co authentication failed (HTTP {response.status})"
                )
            data = await response.json()

        token = data.get("cccToken")
        if not token:
            raise HomeAssistantError("Legacy Lynk & Co authentication returned no CCC token")
        self._ccc_token = token
        return token

    async def _get_user_id(self, vin: str) -> str:
        if self._user_id:
            return self._user_id

        ccc_token = await self._get_ccc_token()
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "Authorization": f"Bearer {ccc_token}",
        }
        self._warn_legacy_tls()
        async with self._session.get(
            DELEGATED_DRIVER_URL.format(vin=vin), headers=headers, ssl=False
        ) as response:
            if response.status != 200:
                _LOGGER.error(
                    "Legacy 01 driver lookup failed (HTTP %s)", response.status
                )
                raise HomeAssistantError(
                    f"Legacy Lynk & Co driver lookup failed (HTTP {response.status})"
                )
            data = await response.json()

        drivers = data.get("drivers") or []
        user_id = drivers[0].get("userId") if drivers else None
        if not user_id:
            raise HomeAssistantError("No legacy Lynk & Co driver was returned")
        self._user_id = user_id
        return user_id

    async def _send_climate(self, vin: str, payload: dict, *, command: str) -> None:
        ccc_token = await self._get_ccc_token()
        user_id = await self._get_user_id(vin)
        headers = {
            "user-agent": LEGACY_USER_AGENT,
            "accept": "application/json",
            "content-type": "application/json",
            "userId": user_id,
            "Authorization": f"Bearer {ccc_token}",
        }

        self._warn_legacy_tls()
        async with self._session.post(
            LEGACY_CLIMATE_URL.format(vin=vin),
            headers=headers,
            json=payload,
            ssl=False,
        ) as response:
            if response.status != 200:
                if response.status in (401, 403):
                    self._ccc_token = None
                    self._user_id = None
                _LOGGER.error(
                    "Legacy 01 climate %s command failed (HTTP %s)",
                    command,
                    response.status,
                )
                raise HomeAssistantError(
                    f"Legacy Lynk & Co climate {command} failed (HTTP {response.status})"
                )

        _LOGGER.info("Legacy Lynk & Co 01 climate %s command accepted", command)

    async def start_climate(
        self,
        vin: str,
        *,
        level: str = "MEDIUM",
        duration_minutes: int = DEFAULT_CLIMATE_DURATION_MINUTES,
    ) -> None:
        level = level.upper()
        if level not in {"LOW", "MEDIUM", "HIGH"}:
            raise ValueError("Legacy climate level must be LOW, MEDIUM or HIGH")
        duration_minutes = max(
            1, min(int(duration_minutes), MAX_CLIMATE_DURATION_MINUTES)
        )
        payload = {
            "climateLevel": level,
            "command": "START",
            "dayofweek": ["ONCE"],
            "durationInSeconds": duration_minutes * 60,
            "scheduledTime": 10,
            "heatItems": ["ALL"],
            "startTimeOfDay": "00:00",
            "timerId": "1",
            "ventilationItems": ["ALL"],
        }
        await self._send_climate(vin, payload, command="START")

    async def stop_climate(self, vin: str) -> None:
        """Stop legacy pre-conditioning.

        Some pre-2025 vehicles accept the historical minimal STOP payload but
        keep the running climate timer active. Sending a complete climate
        payload (matching the START command shape) reliably tells the vehicle
        which timer and climate functions must be cancelled.
        """
        payload = {
            "climateLevel": "MEDIUM",
            "command": "STOP",
            "dayofweek": ["ONCE"],
            "durationInSeconds": 1,
            "scheduledTime": 10,
            "heatItems": ["ALL"],
            "startTimeOfDay": "00:00",
            "timerId": "1",
            "ventilationItems": ["ALL"],
        }
        await self._send_climate(vin, payload, command="STOP")
