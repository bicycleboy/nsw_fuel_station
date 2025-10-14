"""Asynchronous API client for the NSW Fuel API."""

from __future__ import annotations

import logging
import time
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession

from .const import AUTH_URL, BASE_URL, PRICE_ENDPOINT, REFERENCE_ENDPOINT

_LOGGER = logging.getLogger(__name__)
HTTP_UNAUTHORIZED = 401


class NSWFuelApiClientError(Exception):
    """General API error."""


class NSWFuelApiClientAuthError(NSWFuelApiClientError):
    """Authentication failure."""


class NSWFuelApiClient:
    """API client for NSW FuelCheck."""

    def __init__(
            self, session: ClientSession, client_id: str, client_secret: str) -> None:
        """Initialize with aiohttp session and client credentials."""
        self._session = session
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: str | None = None
        self._token_expiry: float = 0

    async def _async_get_token(self) -> str:
        """Get or refresh OAuth2 token."""
        now = time.time()
        if not self._token or now > self._token_expiry - 60:
            _LOGGER.debug("Refreshing NSW Fuel API token")
            data = {
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            }
            try:
                async with self._session.post(AUTH_URL, data=data) as resp:
                    resp.raise_for_status()
                    result = await resp.json()
            except ClientResponseError as err:
                if err.status == HTTP_UNAUTHORIZED:
                    msg = "Invalid client credentials"
                    raise NSWFuelApiClientAuthError(msg) from err
                msg = f"Token request failed with status {err.status}: {err.message}"
                raise NSWFuelApiClientError(msg) from err
            except ClientError as err:
                msg = f"Network error fetching token: {err}"
                raise NSWFuelApiClientError(msg) from err

            self._token = result.get("access_token")
            expires_in = result.get("expires_in", 3600)
            self._token_expiry = now + expires_in

        return self._token

    async def _async_request(
            self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Perform authorized GET request."""
        token = await self._async_get_token()
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{BASE_URL}{path}"

        try:
            async with self._session.get(
                url, headers=headers, params=params, timeout=30) as resp:
                if resp.status == HTTP_UNAUTHORIZED:
                    _LOGGER.warning("Token expired unexpectedly, refreshing...")
                    self._token = None
                    # Try once more with a new token
                    token = await self._async_get_token()
                    headers["Authorization"] = f"Bearer {token}"
                    async with self._session.get(
                        url, headers=headers, params=params, timeout=30) as retry:
                        retry.raise_for_status()
                        return await retry.json()

                resp.raise_for_status()
                return await resp.json()

        except ClientResponseError as err:
            if err.status == HTTP_UNAUTHORIZED:
                msg = "Authentication failed during request"
                raise NSWFuelApiClientAuthError(msg) from err
            msg = f"HTTP error {err.status}: {err.message}"
            raise NSWFuelApiClientError(msg) from err

        except ClientError as err:
            msg = f"Connection error: {err}"
            raise NSWFuelApiClientError(msg) from err

        except Exception as err:
            msg = f"Unexpected error: {err}"
            raise NSWFuelApiClientError(msg) from err

    async def async_get_reference_data(self) -> dict[str, Any]:
        """Fetch reference data (weekly)."""
        return await self._async_request(REFERENCE_ENDPOINT)

    async def async_get_station_price(self, station_code: str) -> dict[str, Any]:
        """Fetch station price (daily)."""
        return await self._async_request(
            PRICE_ENDPOINT.format(station_code=station_code)
        )
