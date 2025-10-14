"""Config flow for NSW Fuel integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import NSWFuelApiClient, NSWFuelApiClientError, NSWFuelApiClientAuthError
from .const import DOMAIN, LOGGER

CONF_STATION_CODE = "station_code"


class NSWFuelConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for NSW Fuel."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await self._test_credentials(
                    client_id=user_input[CONF_CLIENT_ID],
                    client_secret=user_input[CONF_CLIENT_SECRET],
                )
            except NSWFuelApiClientAuthError as err:
                LOGGER.warning("Authentication failed: %s", err)
                errors["base"] = "auth"
            except NSWFuelApiClientError as err:
                LOGGER.error("Error connecting to NSW Fuel API: %s", err)
                errors["base"] = "connection"
            else:
                # Use station_code as part of the unique ID for this config entry
                unique_id = f"{user_input[CONF_CLIENT_ID]}-{user_input[CONF_STATION_CODE]}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"NSW Fuel ({user_input[CONF_STATION_CODE]})",
                    data=user_input,
                )

        # Show the form with selectors and defaults
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_CLIENT_ID,
                        default=(user_input or {}).get(CONF_CLIENT_ID, vol.UNDEFINED),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                    ),
                    vol.Required(
                        CONF_CLIENT_SECRET,
                        default=(user_input or {}).get(CONF_CLIENT_SECRET, vol.UNDEFINED),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                    ),
                    vol.Required(
                        CONF_STATION_CODE,
                        default=(user_input or {}).get(CONF_STATION_CODE, vol.UNDEFINED),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                    ),
                }
            ),
            errors=errors,
        )

    async def _test_credentials(self, client_id: str, client_secret: str) -> None:
        """Validate credentials by fetching a token."""
        session = async_create_clientsession(self.hass)
        client = NSWFuelApiClient(session=session, client_id=client_id, client_secret=client_secret)

        # Attempt to fetch reference data as a quick test
        try:
            await client.async_get_reference_data()
        except NSWFuelApiClientAuthError:
            raise
        except NSWFuelApiClientError as err:
            raise
