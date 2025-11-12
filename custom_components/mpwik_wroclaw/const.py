"""Constants for the MPWiK Wrocław integration."""
from datetime import timedelta

DOMAIN = "mpwik_wroclaw"

# Configuration keys
CONF_SELENIUM_HOST = "selenium_host"
CONF_PUNKT_SIECI = "punkt_sieci"

# Default values
DEFAULT_SELENIUM_HOST = "5f203b37-selenium-standalone-chrome"
DEFAULT_SCAN_INTERVAL = timedelta(hours=12)

# Sensor types
SENSOR_DAILY_CONSUMPTION = "daily_consumption"
SENSOR_HOURLY_CONSUMPTION = "hourly_consumption"
SENSOR_TOTAL_CONSUMPTION = "total_consumption"
SENSOR_LAST_READING = "last_reading"
