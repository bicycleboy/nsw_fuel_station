"""DataUpdateCoordinator for nsw_fuel_ui."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta,timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NSWFuelApiClientAuthError,NSWFuelApiClientError
from .const import REF_DATA_REFRESH_DAYS

_LOGGER = logging.getLogger(__name__)


class NSWFuelCoordinator(DataUpdateCoordinator):
    """Manage data updates from the NSW Fuel API."""

    def __init__(self, hass: HomeAssistant, api: Any, station_code: str) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"nsw_fuel_{station_code}",
            update_interval=timedelta(hours=24),
        )
        self.api = api
        self.station_code = station_code
        self._last_ref_update = datetime.min.replace(tzinfo=timezone.UTC)
        self._reference_data = None

    def _needs_ref_update(self, now: datetime) -> bool:
        """Return True if reference data should be refreshed."""
        return ((now - self._last_ref_update).days >= REF_DATA_REFRESH_DAYS
         or self._reference_data is None)

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            now = datetime.now(timezone.UTC)
            # Refresh reference data monthly or alternaitve
            if self._needs_ref_update(now):
                self._reference_data = await self.api.async_get_reference_data()
                self._last_ref_update = now

            # Fetch station prices daily
            price_data = await self.api.async_get_station_price(self.station_code)
            return {
                "reference": self._reference_data,
                "prices": price_data,
            }
        except NSWFuelApiClientAuthError as err:
            msg = "Authentication failed"
            raise ConfigEntryAuthFailed(msg) from err

        except NSWFuelApiClientError as err:
            msg = f"Error fetching NSW Fuel data: {err}"
            raise UpdateFailed(msg) from err
