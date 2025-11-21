"""Config flow for NSW Fuel integration."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from nsw_fuel import (
    NSWFuelApiClient,
    NSWFuelApiClientAuthError,
    NSWFuelApiClientError,
)
from nsw_fuel.dto import Station

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from homeassistant import config_entries
    from nsw_fuel.client import StationPrice

CONF_SELECTED_STATIONS = "selected_station_codes"
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"

DEFAULT_RADIUS_METERS = 10  # 10 km
STATION_LIST_LIMIT = 20
SENSOR_FUEL_TYPES = ["U91", "E10"]


def _format_station_option(sp: StationPrice) -> str:
    """Return a user-friendly label for a StationPrice for selector options."""
    st = sp.station
    return f"{st.name} - {st.address} - ({st.code})"


def _extract_code_from_option(option_label: str) -> int:
    """Extract station code from formatted option label (last parenthesized number)."""
    try:
        idx = option_label.rfind("(")
        if idx == -1:
            raise ValueError("missing station code in label")
        code_str = option_label[idx + 1 : -1]
        return int(code_str)
    except Exception as err:
        raise ValueError(
            f"Could not parse station code from '{option_label}': {err}"
        ) from err


class NSWFuelConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NSW Fuel."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow state."""
        self._user_inputs: dict[str, Any] = {}
        self._nearby_station_prices: list[StationPrice] = []
        self._station_info: dict[int, Station] = {}

    def _build_user_schema(self, user_input: dict | None = None) -> vol.Schema:
        """Build the schema for the credentials screen."""
        user = user_input or {}
        suggested_client_id = os.getenv("NSWFUELCHECKAPI_KEY", "")
        suggested_client_secret = os.getenv("NSWFUELCHECKAPI_SECRET", "")

        # Default latitude and longitude from Home Assistant config (fallback to empty string)
        suggested_lat = str(getattr(self.hass.config, "latitude", ""))
        suggested_lon = str(getattr(self.hass.config, "longitude", ""))

        return vol.Schema(
            {
                vol.Required(
                    CONF_CLIENT_ID,
                    default=user.get(CONF_CLIENT_ID, vol.UNDEFINED),
                    description={"suggested_value": suggested_client_id},
                ): selector.TextSelector(),
                vol.Required(
                    CONF_CLIENT_SECRET,
                    default=user.get(CONF_CLIENT_SECRET, vol.UNDEFINED),
                    description={"suggested_value": suggested_client_secret},
                ): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
                vol.Required(
                    CONF_LATITUDE,
                    default=user.get(CONF_LATITUDE, suggested_lat),
                    description={
                        "suggested_value": suggested_lat,
                        "placeholder": "e.g. -33.8688",
                    },
                ): selector.selector(
                    {
                        "text": {

                            "type": "text",
                            "multiline": False,
                        }
                    }
                ),
                vol.Required(
                    CONF_LONGITUDE,
                    default=user.get(CONF_LONGITUDE, suggested_lon),
                    description={
                        "suggested_value": suggested_lon,
                        "placeholder": "e.g. 151.2093",
                    },
                ): selector.selector(
                    {
                        "text": {

                            "type": "text",
                            "multiline": False,
                        }
                    }
                ),
            }
        )

    def _build_station_schema(
        self, options: list[str], user_input: dict | None = None
    ) -> vol.Schema:
        """Build the schema for the station selection screen (multi-select dropdown)."""
        user = user_input or {}
        select_selector = selector.selector(
            {
                "select": {
                    "options": options,
                    "mode": "dropdown",
                    "multiple": True,
                    "sort": False,
                }
            }
        )
        return vol.Schema(
            {
                vol.Required(
                    CONF_SELECTED_STATIONS,
                    default=user.get(CONF_SELECTED_STATIONS, []),
                ): select_selector,
            }
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Initial step: authenticate and fetch stations using provided lat/lon."""
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=self._build_user_schema(),
                errors=errors,
            )

        # Store inputs for later steps
        self._user_inputs.update(user_input)

        try:
            lat = float(user_input[CONF_LATITUDE])
            lon = float(user_input[CONF_LONGITUDE])
        except (ValueError, TypeError):
            errors["base"] = "invalid_coordinates"
            return self.async_show_form(
                step_id="user",
                data_schema=self._build_user_schema(user_input),
                errors=errors,
            )

        # Bounding box validation (top-left: -28, 140; bottom-right: -50, 154)
        # Latitude must be between -50 (bottom) and -28 (top)
        # Longitude must be between 140 (left) and 154 (right)
        if not (-50 <= lat <= -28) or not (140 <= lon <= 154):
            errors["base"] = "invalid_coordinates"
            return self.async_show_form(
                step_id="user",
                data_schema=self._build_user_schema(user_input),
                errors=errors,
            )

        session = async_create_clientsession(self.hass)
        client = NSWFuelApiClient(
            session=session,
            client_id=user_input[CONF_CLIENT_ID],
            client_secret=user_input[CONF_CLIENT_SECRET],
        )

        try:
            LOGGER.debug("Fetching nearby stations for authentication check")
            nearby: list[StationPrice] = await client.get_fuel_prices_within_radius(
                latitude=lat,
                longitude=lon,
                radius=DEFAULT_RADIUS_METERS,
                fuel_type="U91",
            )
            # Allow zero stations (valid creds but no stations nearby)
            self._nearby_station_prices = nearby[:STATION_LIST_LIMIT]

            # Build station info cache with Station objects keyed by station code
            self._station_info = {
                sp.station.code: sp.station for sp in self._nearby_station_prices
            }

        except NSWFuelApiClientAuthError as err:
            LOGGER.error("Invalid NSW Fuel API credentials: %s", err)
            errors["base"] = "auth"
            return self.async_show_form(
                step_id="user",
                data_schema=self._build_user_schema(user_input),
                errors=errors,
            )
        except NSWFuelApiClientError as err:
            LOGGER.error("Error communicating with NSW Fuel API: %s", err)
            errors["base"] = "connection"
            return self.async_show_form(
                step_id="user",
                data_schema=self._build_user_schema(user_input),
                errors=errors,
            )

        # Success: show station selection screen
        return await self.async_step_station_select()

    async def async_step_station_select(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Present nearby stations for user to select and save."""

        errors: dict[str, str] = {}

        options = [_format_station_option(sp) for sp in self._nearby_station_prices]

        if user_input is None:
            return self.async_show_form(
                step_id="station_select",
                data_schema=self._build_station_schema(options),
                errors=errors,
            )

        # Extract selected station codes from user selections
        selected_labels: list[str] = user_input.get(CONF_SELECTED_STATIONS, [])
        try:
            selected_codes: list[int] = [
                _extract_code_from_option(lbl) for lbl in selected_labels
            ]
        except ValueError as err:
            LOGGER.exception("Failed to parse selected station label")
            errors["base"] = "invalid_selection"
            return self.async_show_form(
                step_id="station_select",
                data_schema=self._build_station_schema(options, user_input),
                errors=errors,
            )

        if not selected_codes:
            errors["base"] = "no_stations"
            return self.async_show_form(
                step_id="station_select",
                data_schema=self._build_station_schema(options, user_input),
                errors=errors,
            )

        # Create unique id from client id + first selected station
        client_id = self._user_inputs[CONF_CLIENT_ID]
        unique_id = f"{client_id}-{selected_codes[0]}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        # Build config entry data to store
        entry_data = {
            CONF_CLIENT_ID: self._user_inputs[CONF_CLIENT_ID],
            CONF_CLIENT_SECRET: self._user_inputs[CONF_CLIENT_SECRET],
            CONF_LATITUDE: lat,
            CONF_LONGITUDE: lon,
            CONF_SELECTED_STATIONS: selected_codes,
            "station_info": {code: self._station_info[code] for code in selected_codes},
        }

        title = f"NSW Fuel ({selected_codes[0]})"
        return self.async_create_entry(title=title, data=entry_data)
