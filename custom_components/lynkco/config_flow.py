"""Config flow for Lynk & Co integration."""

import logging
import uuid

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, OptionsFlow
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
    DRIVING_SCAN_INTERVAL,
)
from .security import create_pin_hash

_LOGGER = logging.getLogger(__name__)

# This is a transient options-flow field only. The clear-text PIN is never
# stored in the config entry; only a PBKDF2 hash and random salt are persisted.
CONF_SECURITY_PIN_INPUT = "security_pin"


class LynkCoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Lynk & Co."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        return LynkCoOptionsFlow(config_entry)

    def __init__(self) -> None:
        """Initialize."""
        self._auth_url: str | None = None
        self._code_verifier: str | None = None
        self._code_challenge: str | None = None

    async def async_step_user(self, user_input=None):
        """Step 1: Generate auth URL and show it to the user."""
        self._auth_url, self._code_verifier, self._code_challenge = (
            LynkCoAPI.generate_auth_url()
        )

        return self.async_show_form(
            step_id="auth_url",
            description_placeholders={"auth_url": self._auth_url},
            data_schema=vol.Schema({}),
        )

    async def async_step_auth_url(self, user_input=None):
        """Step 2: User has opened the URL — ask for the redirect."""
        return self.async_show_form(
            step_id="paste_redirect",
            data_schema=vol.Schema(
                {vol.Required("redirect_url"): str}
            ),
            errors={},
        )

    async def async_step_paste_redirect(self, user_input=None):
        """Step 3: Exchange the code for tokens."""
        errors = {}

        if user_input is not None:
            redirect_url = user_input["redirect_url"].strip()
            code = LynkCoAPI.extract_code_from_url(redirect_url)

            if not code:
                # Maybe the user pasted just the code
                code = redirect_url if len(redirect_url) > 100 else None

            if not code:
                errors["redirect_url"] = "no_code"
            else:
                session = async_get_clientsession(self.hass)
                tokens = await LynkCoAPI.exchange_code(
                    session, code, self._code_verifier
                )

                if tokens is None:
                    errors["redirect_url"] = "exchange_failed"
                else:
                    access_token = tokens.get("access_token", "")
                    refresh_token = tokens.get("refresh_token", "")
                    device_id = str(uuid.uuid4())

                    if not access_token:
                        errors["redirect_url"] = "no_token"
                    else:
                        # Validate by calling the API
                        api = LynkCoAPI(
                            session, access_token, refresh_token, device_id
                        )
                        if not await api.validate_session():
                            errors["redirect_url"] = "session_failed"
                        else:
                            vehicles = await api.get_vehicles()
                            if not vehicles:
                                errors["redirect_url"] = "no_vehicles"
                            else:
                                # Use email as unique ID
                                await self.async_set_unique_id(api.user_email)
                                self._abort_if_unique_id_configured()

                                return self.async_create_entry(
                                    title=f"Lynk & Co ({api.user_email})",
                                    data={
                                        CONF_ACCESS_TOKEN: access_token,
                                        CONF_REFRESH_TOKEN: refresh_token,
                                        CONF_DEVICE_ID: device_id,
                                    },
                                )

        return self.async_show_form(
            step_id="paste_redirect",
            data_schema=vol.Schema(
                {vol.Required("redirect_url"): str}
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data=None):
        """Handle re-authentication."""
        return await self.async_step_user()


class LynkCoOptionsFlow(OptionsFlow):
    """Handle options for Lynk & Co."""

    def __init__(self, config_entry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        errors = {}
        current = self._config_entry.options

        if user_input is not None:
            new_options = dict(user_input)
            pin = str(new_options.pop(CONF_SECURITY_PIN_INPUT, "")).strip()

            if pin:
                if not pin.isdigit() or not 4 <= len(pin) <= 8:
                    errors[CONF_SECURITY_PIN_INPUT] = "invalid_security_pin"
                else:
                    salt, pin_hash = create_pin_hash(pin)
                    new_options[CONF_SECURITY_PIN_SALT] = salt
                    new_options[CONF_SECURITY_PIN_HASH] = pin_hash
            else:
                # Blank means: keep the existing PIN hash, if configured.
                if current.get(CONF_SECURITY_PIN_SALT):
                    new_options[CONF_SECURITY_PIN_SALT] = current[CONF_SECURITY_PIN_SALT]
                if current.get(CONF_SECURITY_PIN_HASH):
                    new_options[CONF_SECURITY_PIN_HASH] = current[CONF_SECURITY_PIN_HASH]

            if not errors:
                return self.async_create_entry(title="", data=new_options)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL // 60),
                ): vol.All(vol.Coerce(int), vol.Range(min=15, max=180)),
                vol.Required(
                    CONF_DRIVING_INTERVAL,
                    default=current.get(CONF_DRIVING_INTERVAL, DRIVING_SCAN_INTERVAL // 60),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                vol.Required(
                    CONF_SECURITY_ENABLED,
                    default=current.get(CONF_SECURITY_ENABLED, DEFAULT_SECURITY_ENABLED),
                ): bool,
                vol.Required(
                    CONF_SECURITY_AUTH_MINUTES,
                    default=current.get(
                        CONF_SECURITY_AUTH_MINUTES, DEFAULT_SECURITY_AUTH_MINUTES
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=15)),
                vol.Optional(CONF_SECURITY_PIN_INPUT, default=""): str,
            }),
            errors=errors,
        )
