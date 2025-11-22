"""Config flow for NSW Fuel integration."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import homeassistant.helpers.config_validation as cv
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

from .const import (
    ATTRIBUTION,
    DOMAIN,
    LAT_CAMERON_CORNER_BOUND,
    LAT_SE_BOUND,
    LOGGER,
    LON_CAMERON_CORNER_BOUND,
    LON_SE_BOUND,
)

if TYPE_CHECKING:
    from homeassistant import config_entries
    from nsw_fuel.client import StationPrice
    from nsw_fuel.dto import Station

CONF_SELECTED_STATIONS = "selected_station_codes"
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"

DEFAULT_RADIUS_METERS = 10  # 10 km
STATION_LIST_LIMIT = 20
SENSOR_FUEL_TYPES = ["U91", "E10"]


def _format_station_option(sp: StationPrice) -> str:
    """Return a user-friendly station label."""
    LOGGER.debug("_format_station_option entered")
    st = sp.station
    return f"{st.name} - {st.address} ({st.code})"


class NSWFuelConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NSW Fuel."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow state."""
        self._user_inputs: dict[str, Any] = {}
        self._nearby_station_prices: list[StationPrice] = []
        self._station_info: dict[int, Station] = {}
        self._lat: float | None = None
        self._lon: float | None = None

    #
    # ───────────────────────────────────────────────────────────────
    #   USER STEP (Credentials + Coordinates)
    # ───────────────────────────────────────────────────────────────
    #

    def _build_user_schema(self, user_input: dict | None = None) -> vol.Schema:
        """Build schema for credential + coordinate entry."""
        user = user_input or {}
        if user_input is None:
            suggested_client_id = os.getenv("NSWFUELCHECKAPI_KEY", "")
            suggested_client_secret = os.getenv("NSWFUELCHECKAPI_SECRET", "")

            suggested_lat = str(getattr(self.hass.config, "latitude", ""))
            suggested_lon = str(getattr(self.hass.config, "longitude", ""))
        else:
            # On re-show due to errors, use user's last input values as defaults
            suggested_client_id = user_input.get(CONF_CLIENT_ID, "")
            suggested_client_secret = user_input.get(CONF_CLIENT_SECRET, "")
            suggested_lat = user_input.get(CONF_LATITUDE, "")
            suggested_lon = user_input.get(CONF_LONGITUDE, "")

        return vol.Schema(
            {
                # API key
                vol.Required(
                    CONF_CLIENT_ID,
                    default=user.get(CONF_CLIENT_ID, vol.UNDEFINED),
                    description={"suggested_value": suggested_client_id},
                ): selector.TextSelector(),
                # API secret
                vol.Required(
                    CONF_CLIENT_SECRET,
                    default=user.get(CONF_CLIENT_SECRET, vol.UNDEFINED),
                    description={"suggested_value": suggested_client_secret},
                ): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
                # Latitude (simple text field)
                vol.Required(
                    CONF_LATITUDE,
                    default=user.get(CONF_LATITUDE, suggested_lat),
                    description={
                        "suggested_value": suggested_lat,
                        "placeholder": "e.g. -41.64660",
                    },
                ): selector.TextSelector(),
                # Longitude (simple text field)
                vol.Required(
                    CONF_LONGITUDE,
                    default=user.get(CONF_LONGITUDE, suggested_lon),
                    description={
                        "suggested_value": suggested_lon,
                        "placeholder": "e.g. 145.94987",
                    },
                ): selector.TextSelector(),
            }
        )

    #
    # ───────────────────────────────────────────────────────────────
    #   STATION SELECTION STEP
    # ───────────────────────────────────────────────────────────────
    #

    def _build_station_schema(
        self, user_input: dict[str, Any] | None = None
    ) -> vol.Schema:
        """Build schema for station selection."""
        user = user_input or {}
        LOGGER.debug("_build_station_schema entered")
        # Build proper label/value options
        options = [
            {
                "label": _format_station_option(sp),
                "value": str(sp.station.code),
            }
            for sp in self._nearby_station_prices
        ]

        try:
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
        except Exception as err:
            LOGGER.error("Error building select selector: %s", err)
            raise
        LOGGER.debug("_build_station_schema exit")
        return vol.Schema(
            {
                vol.Required(
                    CONF_SELECTED_STATIONS,
                    default=user.get(CONF_SELECTED_STATIONS, []),
                ): select_selector,
            }
        )

    #
    # ───────────────────────────────────────────────────────────────
    #   User / Authentication
    # ───────────────────────────────────────────────────────────────
    #

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Authenticate and fetch stations using provided lat/lon."""
        errors: dict[str, str] = {}

        #
        # First form display
        #
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=self._build_user_schema(),
                errors=errors,
                description_placeholders={"attribution": ATTRIBUTION},
            )

        self._user_inputs.update(user_input)

        #
        # Validate coordinates using HA validators
        #
        try:
            lat = cv.latitude(user_input[CONF_LATITUDE])
            lon = cv.longitude(user_input[CONF_LONGITUDE])
        except vol.Invalid:
            errors["base"] = "invalid_coordinates"
            return self.async_show_form(
                step_id="user",
                data_schema=self._build_user_schema(user_input),
                errors=errors,
                description_placeholders={"attribution": ATTRIBUTION},
            )

        #
        # NSW bounding box validation
        #
        if not (LAT_SE_BOUND <= lat <= LAT_CAMERON_CORNER_BOUND) or not (
            LON_CAMERON_CORNER_BOUND <= lon <= LON_SE_BOUND
        ):
            errors["base"] = "invalid_coordinates"
            return self.async_show_form(
                step_id="user",
                data_schema=self._build_user_schema(user_input),
                errors=errors,
                description_placeholders={"attribution": ATTRIBUTION},
            )

        self._lat = lat
        self._lon = lon

        #
        # Validate credentials + fetch stations
        #
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

            self._nearby_station_prices = nearby[:STATION_LIST_LIMIT]
            self._station_info = {
                sp.station.code: sp.station for sp in self._nearby_station_prices
            }

        except NSWFuelApiClientAuthError:
            errors["base"] = "auth"
            return self.async_show_form(
                step_id="user",
                data_schema=self._build_user_schema(user_input),
                errors=errors,
            )

        except NSWFuelApiClientError as err:
            LOGGER.error("NSW Fuel API error: %s", err)
            errors["base"] = "connection"
            return self.async_show_form(
                step_id="user",
                data_schema=self._build_user_schema(user_input),
                errors=errors,
            )

        LOGGER.debug("returning async_step_station_select")

        return await self.async_step_station_select()

    #
    # ───────────────────────────────────────────────────────────────
    #   Station selection screen
    # ───────────────────────────────────────────────────────────────
    #

    async def async_step_station_select(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Display and handle multi-select for stations."""
        errors: dict[str, str] = {}

        LOGGER.debug("station_select entered")

        #
        # First display
        #
        if user_input is None:
            return self.async_show_form(
                step_id="station_select",
                data_schema=self._build_station_schema(),
                errors=errors,
            )

        #
        # Convert selected station codes to integers
        #
        selected_codes_str: list[str] = user_input.get(CONF_SELECTED_STATIONS, [])
        selected_codes = [int(code_str) for code_str in selected_codes_str]

        if not selected_codes:
            errors["base"] = "no_stations"
            return self.async_show_form(
                step_id="station_select",
                data_schema=self._build_station_schema(user_input),
                errors=errors,
            )

        #
        # Unique ID based on client ID + first selected station
        #
        client_id = self._user_inputs[CONF_CLIENT_ID]
        unique_id = f"{client_id}-{selected_codes[0]}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        #
        # Build entry
        #
        entry_data = {
            CONF_CLIENT_ID: client_id,
            CONF_CLIENT_SECRET: self._user_inputs[CONF_CLIENT_SECRET],
            CONF_LATITUDE: self._lat,
            CONF_LONGITUDE: self._lon,
            CONF_SELECTED_STATIONS: selected_codes,
            "station_info": {code: self._station_info[code] for code in selected_codes},
        }

        title = f"NSW Fuel ({selected_codes[0]})"
        return self.async_create_entry(title=title, data=entry_data)
