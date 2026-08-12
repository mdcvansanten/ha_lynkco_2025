"""Lynk & Co integration for Home Assistant."""

import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import LynkCoAPI
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_ID,
    CONF_DRIVING_INTERVAL,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_SECURITY_AUTH_MINUTES,
    CONF_SECURITY_ENABLED,
    CONF_SECURITY_PIN_HASH,
    CONF_SECURITY_PIN_SALT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SECURITY_AUTH_MINUTES,
    DEFAULT_SECURITY_ENABLED,
    DOMAIN,
)
from .coordinator import LynkCoCoordinator
from .security import VehicleSecurityManager

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor", "binary_sensor", "device_tracker", "lock", "switch", "climate", "button"]

ATTR_VIN = "vin"
ATTR_PERCENT = "percent"
ATTR_TEMP = "temp"
ATTR_HEATERS = "heaters"
ATTR_PIN = "pin"

VALID_HEATERS = [
    "front_left_seat",
    "front_right_seat",
    "rear_left_seat",
    "rear_right_seat",
    "steering_wheel",
    "defrost",
]

OPTIONAL_HEATERS = {
    "rear_left_seat": "rearLeftSeat",
    "rear_right_seat": "rearRightSeat",
    "steering_wheel": "steeringWheel",
}

SERVICE_FLASH_LIGHTS = "flash_lights"
SERVICE_HONK_HORN = "honk_horn"
SERVICE_OPEN_SUNROOF = "open_sunroof"
SERVICE_CLOSE_SUNROOF = "close_sunroof"
SERVICE_SET_CHARGE_LIMIT = "set_charge_limit"
SERVICE_START_CHARGING = "start_charging"
SERVICE_STOP_CHARGING = "stop_charging"
SERVICE_START_VENTILATE = "start_ventilate"
SERVICE_STOP_VENTILATE = "stop_ventilate"
SERVICE_START_HEATERS = "start_heaters"
SERVICE_STOP_HEATERS = "stop_heaters"
SERVICE_START_CONDITIONING = "start_conditioning"
SERVICE_STOP_CONDITIONING = "stop_conditioning"
SERVICE_REFRESH = "refresh"
SERVICE_REQUEST_LOCATION = "request_location"
SERVICE_LOCK_DOOR = "lock_door"
SERVICE_UNLOCK_DOOR = "unlock_door"
SERVICE_LOCK_GLOVEBOX = "lock_glovebox"
SERVICE_UNLOCK_GLOVEBOX = "unlock_glovebox"
SERVICE_AUTHORIZE_SENSITIVE = "authorize_sensitive_commands"
SERVICE_LOCK_SENSITIVE = "lock_sensitive_commands"

ALL_SERVICES = [
    SERVICE_FLASH_LIGHTS, SERVICE_HONK_HORN,
    SERVICE_OPEN_SUNROOF, SERVICE_CLOSE_SUNROOF,
    SERVICE_SET_CHARGE_LIMIT,
    SERVICE_START_CHARGING, SERVICE_STOP_CHARGING,
    SERVICE_START_VENTILATE, SERVICE_STOP_VENTILATE,
    SERVICE_START_HEATERS, SERVICE_STOP_HEATERS,
    SERVICE_START_CONDITIONING, SERVICE_STOP_CONDITIONING,
    SERVICE_REFRESH, SERVICE_REQUEST_LOCATION,
    SERVICE_LOCK_DOOR, SERVICE_UNLOCK_DOOR,
    SERVICE_LOCK_GLOVEBOX, SERVICE_UNLOCK_GLOVEBOX,
    SERVICE_AUTHORIZE_SENSITIVE, SERVICE_LOCK_SENSITIVE,
]

VIN_SCHEMA = vol.Schema({vol.Optional(ATTR_VIN): cv.string})
PIN_SCHEMA = vol.Schema({
    vol.Optional(ATTR_VIN): cv.string,
    vol.Required(ATTR_PIN): cv.string,
})
CHARGE_LIMIT_SCHEMA = vol.Schema({
    vol.Optional(ATTR_VIN): cv.string,
    vol.Required(ATTR_PERCENT): vol.All(vol.Coerce(int), vol.Range(min=50, max=100)),
})
CONDITIONING_SCHEMA = vol.Schema({
    vol.Optional(ATTR_VIN): cv.string,
    vol.Required(ATTR_TEMP): vol.All(vol.Coerce(int), vol.Range(min=16, max=28)),
})
HEATERS_SCHEMA = vol.Schema({
    vol.Optional(ATTR_VIN): cv.string,
    vol.Required(ATTR_HEATERS): vol.All(
        cv.ensure_list, [vol.In(VALID_HEATERS)],
    ),
})
GLOVEBOX_LOCK_SCHEMA = vol.Schema({
    vol.Optional(ATTR_VIN): cv.string,
    vol.Required(ATTR_PIN): vol.All(cv.string, vol.Match(r"^\d{4}$")),
})


def _all_vins(hass: HomeAssistant) -> list[str]:
    """Return all known VINs across all config entries."""
    vins = []
    for entry_data in hass.data.get(DOMAIN, {}).values():
        vins.extend(entry_data.get("coordinators", {}).keys())
    return vins


def _resolve_vin(hass: HomeAssistant, call: ServiceCall) -> str:
    """Get VIN from service call, or auto-detect if only one vehicle."""
    vin = call.data.get(ATTR_VIN)
    if vin:
        return vin
    vins = _all_vins(hass)
    if len(vins) == 1:
        return vins[0]
    raise vol.Invalid(
        f"Multiple vehicles configured ({', '.join(vins)}). Please specify 'vin'."
    )


def _get_entry_data(hass: HomeAssistant, vin: str) -> dict:
    for entry_data in hass.data.get(DOMAIN, {}).values():
        if vin in entry_data.get("coordinators", {}):
            return entry_data
    raise vol.Invalid(f"VIN {vin} not found")


def _get_api(hass: HomeAssistant, vin: str) -> LynkCoAPI:
    """Find the API instance that owns a given VIN."""
    return _get_entry_data(hass, vin)["api"]


def _get_security_manager(hass: HomeAssistant, vin: str) -> VehicleSecurityManager:
    return _get_entry_data(hass, vin)["security"]


def _require_sensitive_authorization(hass: HomeAssistant, vin: str, command: str) -> None:
    """Block high-risk commands unless a temporary PIN window is active."""
    security = _get_security_manager(hass, vin)
    if security.authorized:
        _LOGGER.info("Sensitive vehicle command authorized: %s", command)
        return

    if not security.configured:
        raise HomeAssistantError(
            "Sensitive Lynk & Co commands are locked. Configure a security PIN "
            "in the integration options before using this command."
        )
    raise HomeAssistantError(
        "Sensitive Lynk & Co commands are locked. Call "
        "lynkco.authorize_sensitive_commands with your PIN first."
    )


def _get_coordinator(hass: HomeAssistant, vin: str) -> LynkCoCoordinator | None:
    for entry_data in hass.data.get(DOMAIN, {}).values():
        coordinator = entry_data.get("coordinators", {}).get(vin)
        if coordinator:
            return coordinator
    return None


def _targeted_refresh(hass: HomeAssistant, vin: str, data_key: str, fetch_fn_name: str) -> None:
    """Schedule a targeted refresh of a single data key after an action."""
    coordinator = _get_coordinator(hass, vin)
    if coordinator:
        api = _get_api(hass, vin)
        fetch_fn = getattr(api, fetch_fn_name)
        hass.async_create_task(
            coordinator.async_targeted_refresh(data_key, lambda: fetch_fn(vin))
        )


def _security_from_entry(entry: ConfigEntry) -> VehicleSecurityManager:
    options = entry.options
    return VehicleSecurityManager(
        enabled=options.get(CONF_SECURITY_ENABLED, DEFAULT_SECURITY_ENABLED),
        pin_salt=options.get(CONF_SECURITY_PIN_SALT, ""),
        pin_hash=options.get(CONF_SECURITY_PIN_HASH, ""),
        authorization_minutes=options.get(
            CONF_SECURITY_AUTH_MINUTES, DEFAULT_SECURITY_AUTH_MINUTES
        ),
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Lynk & Co from a config entry."""
    session = async_get_clientsession(hass)

    def _persist_tokens(access_token: str, refresh_token: str) -> None:
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_ACCESS_TOKEN: access_token, CONF_REFRESH_TOKEN: refresh_token},
        )

    api = LynkCoAPI(
        session,
        entry.data[CONF_ACCESS_TOKEN],
        entry.data[CONF_REFRESH_TOKEN],
        entry.data[CONF_DEVICE_ID],
        on_token_refresh=_persist_tokens,
    )

    await api.validate_session()
    vehicles = await api.get_vehicles()

    if not vehicles:
        _LOGGER.error("No vehicles found")
        return False

    coordinators: dict[str, LynkCoCoordinator] = {}
    for vehicle_entry in vehicles:
        vehicle = vehicle_entry.get("vehicle") or {}
        vin = vehicle.get("vin")
        model = vehicle.get("model", "Unknown")
        if not vin:
            continue

        coordinator = LynkCoCoordinator(hass, entry, api, vin, model)
        await coordinator.async_config_entry_first_refresh()
        coordinators[vin] = coordinator
        entry.async_on_unload(coordinator.start_fast_poll())

    security = _security_from_entry(entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": api,
        "coordinators": coordinators,
        "security": security,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _options_updated(_hass, _entry):
        scan_minutes = _entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL // 60)
        for coordinator in coordinators.values():
            coordinator.update_interval = timedelta(minutes=scan_minutes)
        security.update(
            enabled=_entry.options.get(CONF_SECURITY_ENABLED, DEFAULT_SECURITY_ENABLED),
            pin_salt=_entry.options.get(CONF_SECURITY_PIN_SALT, ""),
            pin_hash=_entry.options.get(CONF_SECURITY_PIN_HASH, ""),
            authorization_minutes=_entry.options.get(
                CONF_SECURITY_AUTH_MINUTES, DEFAULT_SECURITY_AUTH_MINUTES
            ),
        )

    entry.async_on_unload(entry.add_update_listener(_options_updated))

    if not hass.services.has_service(DOMAIN, SERVICE_FLASH_LIGHTS):
        async def handle_flash_lights(call: ServiceCall) -> None:
            vin = _resolve_vin(hass, call)
            await _get_api(hass, vin).flash_lights(vin)

        async def handle_honk_horn(call: ServiceCall) -> None:
            vin = _resolve_vin(hass, call)
            await _get_api(hass, vin).honk_horn(vin)

        async def handle_open_sunroof(call: ServiceCall) -> None:
            vin = _resolve_vin(hass, call)
            _require_sensitive_authorization(hass, vin, SERVICE_OPEN_SUNROOF)
            await _get_api(hass, vin).open_sunroof(vin)
            _targeted_refresh(hass, vin, "doors", "get_doors_windows")

        async def handle_close_sunroof(call: ServiceCall) -> None:
            vin = _resolve_vin(hass, call)
            await _get_api(hass, vin).close_sunroof(vin)
            _targeted_refresh(hass, vin, "doors", "get_doors_windows")

        async def handle_set_charge_limit(call: ServiceCall) -> None:
            vin = _resolve_vin(hass, call)
            await _get_api(hass, vin).set_charge_limit(vin, call.data[ATTR_PERCENT])
            _targeted_refresh(hass, vin, "charge", "get_charge_state")

        async def handle_start_charging(call: ServiceCall) -> None:
            vin = _resolve_vin(hass, call)
            await _get_api(hass, vin).start_charging(vin)
            _targeted_refresh(hass, vin, "charge", "get_charge_state")

        async def handle_stop_charging(call: ServiceCall) -> None:
            vin = _resolve_vin(hass, call)
            await _get_api(hass, vin).stop_charging(vin)
            _targeted_refresh(hass, vin, "charge", "get_charge_state")

        async def handle_start_ventilate(call: ServiceCall) -> None:
            vin = _resolve_vin(hass, call)
            await _get_api(hass, vin).start_ventilate(vin)
            _targeted_refresh(hass, vin, "doors", "get_doors_windows")

        async def handle_stop_ventilate(call: ServiceCall) -> None:
            vin = _resolve_vin(hass, call)
            await _get_api(hass, vin).stop_ventilate(vin)
            _targeted_refresh(hass, vin, "doors", "get_doors_windows")

        def _validate_heaters(hass: HomeAssistant, vin: str, heaters: list[str]) -> list[str]:
            coordinator = _get_coordinator(hass, vin)
            if coordinator and coordinator.data:
                available = (coordinator.data.get("climate", {}).get("heaters") or {})
                for h in heaters:
                    api_key = OPTIONAL_HEATERS.get(h)
                    if api_key and available.get(api_key) is None:
                        raise vol.Invalid(f"Heater zone '{h}' is not available on this vehicle")
            return [h.upper() for h in heaters]

        async def handle_start_heaters(call: ServiceCall) -> None:
            vin = _resolve_vin(hass, call)
            heaters = _validate_heaters(hass, vin, call.data[ATTR_HEATERS])
            await _get_api(hass, vin).start_heaters(vin, heaters)
            _targeted_refresh(hass, vin, "climate", "get_climate_state")

        async def handle_stop_heaters(call: ServiceCall) -> None:
            vin = _resolve_vin(hass, call)
            heaters = _validate_heaters(hass, vin, call.data[ATTR_HEATERS])
            await _get_api(hass, vin).stop_heaters(vin, heaters)
            _targeted_refresh(hass, vin, "climate", "get_climate_state")

        async def handle_start_conditioning(call: ServiceCall) -> None:
            vin = _resolve_vin(hass, call)
            await _get_api(hass, vin).start_conditioning(vin, call.data[ATTR_TEMP])
            _targeted_refresh(hass, vin, "climate", "get_climate_state")

        async def handle_stop_conditioning(call: ServiceCall) -> None:
            vin = _resolve_vin(hass, call)
            await _get_api(hass, vin).stop_conditioning(vin)
            _targeted_refresh(hass, vin, "climate", "get_climate_state")

        async def handle_lock_door(call: ServiceCall) -> None:
            vin = _resolve_vin(hass, call)
            await _get_api(hass, vin).lock_door(vin)
            _targeted_refresh(hass, vin, "vehicle_data", "get_vehicle_data")

        async def handle_unlock_door(call: ServiceCall) -> None:
            vin = _resolve_vin(hass, call)
            _require_sensitive_authorization(hass, vin, SERVICE_UNLOCK_DOOR)
            await _get_api(hass, vin).unlock_door(vin)
            _targeted_refresh(hass, vin, "vehicle_data", "get_vehicle_data")

        async def handle_lock_glovebox(call: ServiceCall) -> None:
            vin = _resolve_vin(hass, call)
            await _get_api(hass, vin).lock_glovebox(vin, call.data[ATTR_PIN])
            _targeted_refresh(hass, vin, "vehicle_data", "get_vehicle_data")

        async def handle_unlock_glovebox(call: ServiceCall) -> None:
            vin = _resolve_vin(hass, call)
            _require_sensitive_authorization(hass, vin, SERVICE_UNLOCK_GLOVEBOX)
            await _get_api(hass, vin).unlock_glovebox(vin)
            _targeted_refresh(hass, vin, "vehicle_data", "get_vehicle_data")

        async def handle_request_location(call: ServiceCall) -> None:
            vin = _resolve_vin(hass, call)
            await _get_api(hass, vin).request_location(vin)
            _targeted_refresh(hass, vin, "location", "get_location")

        async def handle_refresh(call: ServiceCall) -> None:
            vin = _resolve_vin(hass, call)
            coordinator = _get_coordinator(hass, vin)
            if coordinator:
                await coordinator.async_request_refresh()
            else:
                raise vol.Invalid(f"VIN {vin} not found")

        async def handle_authorize_sensitive(call: ServiceCall) -> None:
            vin = _resolve_vin(hass, call)
            manager = _get_security_manager(hass, vin)
            if not manager.configured:
                raise HomeAssistantError(
                    "No Lynk & Co vehicle security PIN is configured. Open the "
                    "integration options and set a 4-8 digit PIN first."
                )
            if not manager.authorize(call.data[ATTR_PIN]):
                _LOGGER.warning("Rejected sensitive vehicle authorization attempt")
                raise HomeAssistantError("Invalid Lynk & Co vehicle security PIN")
            _LOGGER.info(
                "Sensitive vehicle commands temporarily authorized for %s minute(s)",
                manager.authorization_minutes,
            )

        async def handle_lock_sensitive(call: ServiceCall) -> None:
            vin = _resolve_vin(hass, call)
            _get_security_manager(hass, vin).lock()
            _LOGGER.info("Sensitive vehicle commands locked")

        hass.services.async_register(DOMAIN, SERVICE_FLASH_LIGHTS, handle_flash_lights, VIN_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_HONK_HORN, handle_honk_horn, VIN_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_OPEN_SUNROOF, handle_open_sunroof, VIN_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_CLOSE_SUNROOF, handle_close_sunroof, VIN_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_SET_CHARGE_LIMIT, handle_set_charge_limit, CHARGE_LIMIT_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_START_CHARGING, handle_start_charging, VIN_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_STOP_CHARGING, handle_stop_charging, VIN_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_START_VENTILATE, handle_start_ventilate, VIN_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_STOP_VENTILATE, handle_stop_ventilate, VIN_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_START_HEATERS, handle_start_heaters, HEATERS_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_STOP_HEATERS, handle_stop_heaters, HEATERS_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_START_CONDITIONING, handle_start_conditioning, CONDITIONING_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_STOP_CONDITIONING, handle_stop_conditioning, VIN_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_LOCK_DOOR, handle_lock_door, VIN_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_UNLOCK_DOOR, handle_unlock_door, VIN_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_LOCK_GLOVEBOX, handle_lock_glovebox, GLOVEBOX_LOCK_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_UNLOCK_GLOVEBOX, handle_unlock_glovebox, VIN_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_REQUEST_LOCATION, handle_request_location, VIN_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_REFRESH, handle_refresh, VIN_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_AUTHORIZE_SENSITIVE, handle_authorize_sensitive, PIN_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_LOCK_SENSITIVE, handle_lock_sensitive, VIN_SCHEMA)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data.get(DOMAIN):
            for service in ALL_SERVICES:
                hass.services.async_remove(DOMAIN, service)
    return unload_ok
