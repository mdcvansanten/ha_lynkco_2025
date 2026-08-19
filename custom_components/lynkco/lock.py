"""Lock platform for Lynk & Co integration."""

import logging

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL_NAMES
from .coordinator import LynkCoCoordinator
from .security import VehicleSecurityManager

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for vin, coordinator in data["coordinators"].items():
        entities.append(LynkCoLock(coordinator, data["api"], data["security"]))
        entities.append(
            LynkCoGloveboxLock(coordinator, data["api"], data["security"])
        )
    async_add_entities(entities)


class _SensitiveUnlockMixin:
    """Shared guard for entity-level unlock operations."""

    _security: VehicleSecurityManager

    def _require_unlock_authorization(self) -> None:
        if self._security.authorized:
            return
        if not self._security.configured:
            raise HomeAssistantError(
                "Sensitive Lynk & Co commands are locked. Configure a vehicle "
                "security PIN in the integration options first."
            )
        raise HomeAssistantError(
            "Sensitive Lynk & Co commands are locked. Use the "
            "lynkco.authorize_sensitive_commands action with your PIN first."
        )


class LynkCoLock(_SensitiveUnlockMixin, CoordinatorEntity, LockEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "door_lock"

    def __init__(
        self,
        coordinator: LynkCoCoordinator,
        api,
        security: VehicleSecurityManager,
    ) -> None:
        super().__init__(coordinator)
        self._api = api
        self._security = security
        self._attr_unique_id = f"{coordinator.vin}_lock"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.vin)},
            "name": MODEL_NAMES.get(self.coordinator.model, f"Lynk & Co {self.coordinator.model}"),
            "manufacturer": MANUFACTURER,
            "model": MODEL_NAMES.get(self.coordinator.model, self.coordinator.model),
            "serial_number": self.coordinator.vin,
        }

    @property
    def is_locked(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        vehicle_data = self.coordinator.data.get("vehicle_data") or {}
        central_lock = vehicle_data.get("centralLock") or {}
        status = central_lock.get("status")
        if status is None:
            return None
        return status == "LOCKED"

    async def async_lock(self, **kwargs) -> None:
        _LOGGER.info("Locking vehicle doors")
        await self._api.lock_door(self.coordinator.vin)
        self.hass.async_create_task(
            self.coordinator.async_targeted_refresh(
                "vehicle_data", lambda: self._api.get_vehicle_data(self.coordinator.vin)
            )
        )

    async def async_unlock(self, **kwargs) -> None:
        self._require_unlock_authorization()
        _LOGGER.info("Unlocking vehicle doors after security authorization")
        await self._api.unlock_door(self.coordinator.vin)
        self.hass.async_create_task(
            self.coordinator.async_targeted_refresh(
                "vehicle_data", lambda: self._api.get_vehicle_data(self.coordinator.vin)
            )
        )


class LynkCoGloveboxLock(_SensitiveUnlockMixin, CoordinatorEntity, LockEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "glovebox_lock"

    def __init__(
        self,
        coordinator: LynkCoCoordinator,
        api,
        security: VehicleSecurityManager,
    ) -> None:
        super().__init__(coordinator)
        self._api = api
        self._security = security
        self._attr_unique_id = f"{coordinator.vin}_glovebox_lock"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.vin)},
            "name": MODEL_NAMES.get(self.coordinator.model, f"Lynk & Co {self.coordinator.model}"),
            "manufacturer": MANUFACTURER,
            "model": MODEL_NAMES.get(self.coordinator.model, self.coordinator.model),
            "serial_number": self.coordinator.vin,
        }

    @property
    def code_format(self) -> str | None:
        if self.is_locked:
            return None
        return r"^\d{4}$"

    @property
    def is_locked(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        glovebox = self.coordinator.data.get("vehicle_data", {}).get("gloveBox")
        if glovebox is None:
            return None
        status = glovebox.get("status")
        if status is None:
            return None
        return status == "LOCKED"

    async def async_lock(self, **kwargs) -> None:
        code = kwargs.get("code")
        if not code:
            raise ValueError("A PIN code is required to lock the glovebox")
        _LOGGER.info("Locking vehicle glovebox")
        await self._api.lock_glovebox(self.coordinator.vin, code)
        self.hass.async_create_task(
            self.coordinator.async_targeted_refresh(
                "vehicle_data", lambda: self._api.get_vehicle_data(self.coordinator.vin)
            )
        )

    async def async_unlock(self, **kwargs) -> None:
        self._require_unlock_authorization()
        _LOGGER.info("Unlocking vehicle glovebox after security authorization")
        await self._api.unlock_glovebox(self.coordinator.vin)
        self.hass.async_create_task(
            self.coordinator.async_targeted_refresh(
                "vehicle_data", lambda: self._api.get_vehicle_data(self.coordinator.vin)
            )
        )
