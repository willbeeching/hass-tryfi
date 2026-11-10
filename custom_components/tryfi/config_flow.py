"""Config, re-authentication and options flows for TryFi."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

# Core 2026.10 replaced voluptuous with probatio, and types every flow schema
# as probatio's. Same API, so the schemas below are written once; voluptuous
# is only reached on the older cores this still supports, where probatio does
# not exist.
try:
    import probatio as vol
except ImportError:
    import voluptuous as vol  # type: ignore[no-redef]

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import TryFiAuthError, TryFiConnectionError, connect
from .const import (
    CONF_PASSWORD,
    CONF_POLLING_RATE,
    CONF_USERNAME,
    DEFAULT_POLLING_RATE,
    DOMAIN,
    MIN_POLLING_RATE,
)
from .coordinator import polling_rate

_LOGGER = logging.getLogger(__name__)

_POLLING = NumberSelector(
    NumberSelectorConfig(
        min=MIN_POLLING_RATE,
        max=3600,
        step=1,
        unit_of_measurement="s",
        mode=NumberSelectorMode.BOX,
    )
)
_PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL)
        ),
        vol.Required(CONF_PASSWORD): _PASSWORD,
        vol.Optional(CONF_POLLING_RATE, default=DEFAULT_POLLING_RATE): _POLLING,
    }
)
STEP_REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): _PASSWORD})


class TryFiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Sign in to TryFi."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowHandler:
        return OptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._sign_in(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_POLLING_RATE: int(user_input[CONF_POLLING_RATE]),
                    },
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._sign_in(
                entry.data[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_SCHEMA,
            description_placeholders={"username": entry.data[CONF_USERNAME]},
            errors=errors,
        )

    async def _sign_in(self, username: str, password: str) -> dict[str, str]:
        """Sign in once to prove the credentials. Returns the form's errors."""
        try:
            tryfi = await self.hass.async_add_executor_job(connect, username, password)
        except TryFiAuthError:
            return {"base": "invalid_auth"}
        except TryFiConnectionError:
            return {"base": "cannot_connect"}
        except Exception:
            _LOGGER.exception("Unexpected error signing in to TryFi")
            return {"base": "unknown"}
        tryfi.session.close()
        return {}


class OptionsFlowHandler(OptionsFlow):
    """Change how often TryFi is polled.

    Takes no config entry: core provides self.config_entry, and assigning it
    here, as upstream did, now fails (upstream sbabcock23/hass-tryfi#113).
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            # Saving triggers the entry's update listener, which reloads it.
            return self.async_create_entry(
                data={CONF_POLLING_RATE: int(user_input[CONF_POLLING_RATE])}
            )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_POLLING_RATE, default=polling_rate(self.config_entry)
                    ): _POLLING,
                }
            ),
        )
