"""Constants for nsw_fuel_ui."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "nsw_fuel_ui"
ATTRIBUTION = "Data provided by https://www.fuelcheck.nsw.gov.au/"
REF_DATA_REFRESH_DAYS = 30
LAT_CAMERON_CORNER_BOUND = -28.99608
LON_CAMERON_CORNER_BOUND = 141.00180
LAT_SE_BOUND = -50
LON_SE_BOUND = 154
