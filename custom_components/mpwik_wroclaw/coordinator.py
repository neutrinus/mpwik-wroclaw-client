"""DataUpdateCoordinator for MPWiK Wrocław integration."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
import random
from typing import Any

from selenium import webdriver

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_PUNKT_SIECI,
    CONF_SELENIUM_HOST,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class MPWiKDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching MPWiK data from API."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        self.entry = entry
        self.login = entry.data[CONF_USERNAME]
        self.password = entry.data[CONF_PASSWORD]
        self.selenium_host = entry.data[CONF_SELENIUM_HOST]
        self.punkt_sieci = entry.data[CONF_PUNKT_SIECI]
        self.client = None
        
        # Add random offset to prevent all instances from updating at the same time
        # This helps avoid overwhelming the MPWiK servers
        random_offset = timedelta(minutes=random.randint(0, 30))
        update_interval = DEFAULT_SCAN_INTERVAL + random_offset
        
        _LOGGER.debug(
            f"Update interval set to {update_interval.total_seconds() / 3600:.1f} hours "
            f"(base: {DEFAULT_SCAN_INTERVAL.total_seconds() / 3600:.1f}h + "
            f"random: {random_offset.total_seconds() / 60:.0f}min)"
        )
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        # Import the mpwik_selenium module
        import sys
        from pathlib import Path
        
        # Add the parent directory to the path so we can import mpwik_selenium
        integration_path = Path(__file__).parent.parent.parent
        if str(integration_path) not in sys.path:
            sys.path.insert(0, str(integration_path))
        
        from mpwik_selenium import MPWiKBrowserClient
        
        def _fetch_data():
            """Fetch data from MPWiK."""
            # Create client with remote WebDriver
            client = MPWiKBrowserClient(
                login=self.login,
                password=self.password,
                headless=True,
                debug=False
            )
            
            # Override the driver setup to use remote WebDriver
            driver_url = f"http://{self.selenium_host}:4444/wd/hub"
            
            def _setup_remote_driver():
                if client.driver is not None:
                    return
                
                options = webdriver.ChromeOptions()
                options.add_argument("--headless=new")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--disable-gpu")
                options.add_argument("--window-size=1920,1080")
                options.add_argument(
                    "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
                )
                options.set_capability("goog:loggingPrefs", {"performance": "ALL", "browser": "ALL"})
                
                client.driver = webdriver.Remote(
                    command_executor=driver_url,
                    options=options
                )
                client.driver.implicitly_wait(10)
                _LOGGER.debug("Remote WebDriver connected successfully")
            
            client._setup_driver = _setup_remote_driver
            
            try:
                # Authenticate
                if not client.authenticate():
                    raise ConfigEntryAuthFailed("Authentication failed")
                
                # Get data for the last 2 days to ensure we have recent readings
                date_to = datetime.now()
                date_from = date_to - timedelta(days=2)
                
                # Fetch daily readings
                daily_readings = client.get_daily_readings(
                    self.login,
                    self.punkt_sieci,
                    date_from,
                    date_to
                )
                
                # Fetch hourly readings for today
                hourly_date_from = date_to.replace(hour=0, minute=0, second=0)
                hourly_readings = client.get_hourly_readings(
                    self.login,
                    self.punkt_sieci,
                    hourly_date_from,
                    date_to
                )
                
                if daily_readings is None and hourly_readings is None:
                    raise UpdateFailed("Failed to fetch readings")
                
                # Process the data
                data = {
                    "daily_readings": daily_readings or [],
                    "hourly_readings": hourly_readings or [],
                    "last_update": datetime.now().isoformat(),
                }
                
                # Calculate latest values
                if daily_readings:
                    # Sort by date to get the latest
                    sorted_daily = sorted(
                        daily_readings,
                        key=lambda x: x.get("data", ""),
                        reverse=True
                    )
                    if sorted_daily:
                        latest_daily = sorted_daily[0]
                        data["latest_daily_consumption"] = latest_daily.get("zuzycie", 0.0)
                        data["latest_daily_reading"] = latest_daily.get("wskazanie", 0.0)
                        data["latest_daily_date"] = latest_daily.get("data")
                
                if hourly_readings:
                    # Sort by date to get the latest
                    sorted_hourly = sorted(
                        hourly_readings,
                        key=lambda x: x.get("data", ""),
                        reverse=True
                    )
                    if sorted_hourly:
                        latest_hourly = sorted_hourly[0]
                        data["latest_hourly_consumption"] = latest_hourly.get("zuzycie", 0.0)
                        data["latest_hourly_reading"] = latest_hourly.get("wskazanie", 0.0)
                        data["latest_hourly_date"] = latest_hourly.get("data")
                
                # Calculate total consumption (sum of all daily readings in the period)
                if daily_readings:
                    total_consumption = sum(r.get("zuzycie", 0.0) for r in daily_readings)
                    data["total_consumption"] = total_consumption
                
                _LOGGER.debug(f"Fetched data: {len(daily_readings or [])} daily, {len(hourly_readings or [])} hourly readings")
                
                return data
                
            finally:
                client.close()
        
        try:
            return await self.hass.async_add_executor_job(_fetch_data)
        except ConfigEntryAuthFailed:
            raise
        except Exception as err:
            _LOGGER.exception("Error fetching MPWiK data")
            raise UpdateFailed(f"Error communicating with API: {err}") from err
