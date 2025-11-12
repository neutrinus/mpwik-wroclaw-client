"""Config flow for MPWiK Wrocław integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from selenium import webdriver
from selenium.common.exceptions import WebDriverException

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_PUNKT_SIECI,
    CONF_SELENIUM_HOST,
    DEFAULT_SELENIUM_HOST,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.
    
    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    # Import the mpwik_selenium module from the repository
    import sys
    from pathlib import Path
    
    # Add the parent directory to the path so we can import mpwik_selenium
    integration_path = Path(__file__).parent.parent.parent
    if str(integration_path) not in sys.path:
        sys.path.insert(0, str(integration_path))
    
    from mpwik_selenium import MPWiKBrowserClient
    
    selenium_host = data[CONF_SELENIUM_HOST]
    login = data[CONF_USERNAME]
    password = data[CONF_PASSWORD]
    punkt_sieci = data[CONF_PUNKT_SIECI]
    
    # Test connection to Selenium and authentication
    try:
        # Setup remote WebDriver connection
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        
        # Create remote driver
        driver_url = f"http://{selenium_host}:4444/wd/hub"
        _LOGGER.debug(f"Connecting to Selenium at {driver_url}")
        
        # Test connection in executor to avoid blocking
        def _test_connection():
            try:
                driver = webdriver.Remote(
                    command_executor=driver_url,
                    options=options
                )
                driver.quit()
                return True
            except Exception as e:
                _LOGGER.error(f"Failed to connect to Selenium: {e}")
                return False
        
        can_connect = await hass.async_add_executor_job(_test_connection)
        
        if not can_connect:
            raise CannotConnect("Failed to connect to Selenium WebDriver")
        
        # Now test authentication with MPWiK
        def _test_auth():
            # Create a temporary client to test authentication
            # We'll create a custom client that uses remote WebDriver
            client = MPWiKBrowserClient(
                login=login,
                password=password,
                headless=True,
                debug=False
            )
            
            # Override the driver setup to use remote WebDriver
            original_setup = client._setup_driver
            
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
            
            client._setup_driver = _setup_remote_driver
            
            try:
                # Try to authenticate (with shorter timeout for config flow)
                authenticated = client.authenticate(max_wait=60)
                
                if not authenticated:
                    raise InvalidAuth("Authentication failed")
                
                # Verify we can get punkty sieci
                punkty = client.get_punkty_sieci(login)
                
                if punkty is None:
                    raise InvalidAuth("Failed to fetch network points")
                
                # Verify the punkt_sieci exists
                punkt_ids = [p.get("id") for p in punkty]
                if punkt_sieci not in punkt_ids:
                    raise InvalidAuth(f"Network point {punkt_sieci} not found")
                
                return True
            finally:
                client.close()
        
        auth_result = await hass.async_add_executor_job(_test_auth)
        
        if not auth_result:
            raise InvalidAuth("Authentication test failed")
        
    except CannotConnect:
        raise
    except InvalidAuth:
        raise
    except Exception as e:
        _LOGGER.exception("Unexpected exception during validation")
        raise CannotConnect(f"Unexpected error: {str(e)}")
    
    # Return info that you want to store in the config entry
    return {"title": f"MPWiK Wrocław - {login}"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MPWiK Wrocław."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(
                    CONF_SELENIUM_HOST, default=DEFAULT_SELENIUM_HOST
                ): str,
                vol.Required(CONF_PUNKT_SIECI): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""
