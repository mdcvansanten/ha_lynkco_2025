"""Climate platform for Lynk & Co integration."""

import logging

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACAction, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL_NAMES
from .coordinator import LynkCoCoordinator
from .legacy_commands import Legacy01Commands

_LOGGER = logging.getLogger(__name__)
DEFAULT_MIN_TEMP = 16
DEFAULT_MAX_TEMP = 28
DEFAULT_TARGET_TEMP = 22
LEGACY_01_MODEL = "CX11_A1"
EVENT_CLIMATE_COMMAND = "lynkco_climate_command"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([LynkCoClimate(coordinator, data["api"]) for coordinator in data["coordinators"].values()])


class LynkCoClimate(CoordinatorEntity, RestoreEntity, ClimateEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "climate"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.AUTO]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, coordinator: LynkCoCoordinator, api) -> None:
        super().__init__(coordinator)
        self._api = api
        self._legacy = Legacy01Commands(api) if coordinator.model == LEGACY_01_MODEL else None
        self._attr_unique_id = f"{coordinator.vin}_climate"
        self._target_temp: float | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.attributes.get("temperature") is not None:
            try:
                self._target_temp = float(last_state.attributes["temperature"])
            except (ValueError, TypeError):
                self._target_temp = None

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self.coordinator.vin)}, "name": MODEL_NAMES.get(self.coordinator.model, f"Lynk & Co {self.coordinator.model}"), "manufacturer": MANUFACTURER, "model": MODEL_NAMES.get(self.coordinator.model, self.coordinator.model), "serial_number": self.coordinator.vin}

    @property
    def _climate(self) -> dict:
        return (self.coordinator.data or {}).get("climate") or {}

    @property
    def current_temperature(self) -> float | None:
        return self._climate.get("interiorTemperature")

    @property
    def target_temperature(self) -> float | None:
        return self._target_temp if self._target_temp is not None else self._climate.get("targetTemperature") or DEFAULT_TARGET_TEMP

    @property
    def min_temp(self) -> float:
        return self._climate.get("minAvailableHvacTemperature") or DEFAULT_MIN_TEMP

    @property
    def max_temp(self) -> float:
        return self._climate.get("maxAvailableHvacTemperature") or DEFAULT_MAX_TEMP

    @property
    def hvac_mode(self) -> HVACMode | None:
        status = self._climate.get("status")
        if status is None:
            return None
        return HVACMode.AUTO if str(status).upper().startswith("ACTIVE") else HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction | None:
        status = self._climate.get("status")
        if status is None:
            return None
        status = str(status).upper()
        if "COOLING" in status:
            return HVACAction.COOLING
        if "HEATING" in status:
            return HVACAction.HEATING
        return HVACAction.OFF

    def _fire_command_event(self, command: str, result: str, target_temp: float | None = None, error_type: str | None = None, legacy_level: str | None = None) -> None:
        """Publish a safe event for HA automations and diagnostics.

        VINs, tokens and account details are deliberately excluded.
        """
        data = {
            "command": command,
            "result": result,
            "entity_id": self.entity_id,
            "legacy_01": self._legacy is not None,
        }
        if target_temp is not None:
            data["target_temperature"] = float(target_temp)
        if legacy_level is not None:
            data["legacy_level"] = legacy_level
        if error_type:
            data["error_type"] = error_type
        self.hass.bus.async_fire(EVENT_CLIMATE_COMMAND, data)

    @staticmethod
    def _legacy_level_for_temperature(temp: float) -> str:
        """Map HA temperature to legacy LOW/MEDIUM/HIGH for controlled testing.

        The old backend does not expose a documented numeric target-temperature
        field. This mapping is intentionally experimental so we can observe the
        actual setpoint shown by the vehicle for each legacy climate level.
        """
        if temp <= 20:
            return "LOW"
        if temp >= 24:
            return "HIGH"
        return "MEDIUM"

    async def _start(self, temp: float) -> None:
        legacy_level = None
        try:
            if self._legacy:
                legacy_level = self._legacy_level_for_temperature(temp)
                _LOGGER.info(
                    "Legacy Lynk & Co 01 climate test mapping: %.1f C -> %s",
                    temp,
                    legacy_level,
                )
                await self._legacy.start_climate(self.coordinator.vin, level=legacy_level)
            else:
                await self._api.start_conditioning(self.coordinator.vin, int(round(temp)))
        except Exception as err:
            self._fire_command_event("START", "failed", temp, type(err).__name__, legacy_level)
            raise
        self._fire_command_event("START", "accepted", temp, legacy_level=legacy_level)

    async def _stop(self) -> None:
        try:
            if self._legacy:
                await self._legacy.stop_climate(self.coordinator.vin)
            else:
                await self._api.stop_conditioning(self.coordinator.vin)
        except Exception as err:
            self._fire_command_event("STOP", "failed", error_type=type(err).__name__)
            raise
        self._fire_command_event("STOP", "accepted")

    async def async_set_temperature(self, **kwargs) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        self._target_temp = float(temp)
        self.async_write_ha_state()
        await self._start(self._target_temp)
        self._refresh_climate()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        else:
            await self.async_turn_on()

    async def async_turn_on(self) -> None:
        await self._start(self.target_temperature or DEFAULT_TARGET_TEMP)
        self._refresh_climate()

    async def async_turn_off(self) -> None:
        await self._stop()
        self._refresh_climate()

    def _refresh_climate(self) -> None:
        self.hass.async_create_task(self.coordinator.async_targeted_refresh("climate", lambda: self._api.get_climate_state(self.coordinator.vin)))
