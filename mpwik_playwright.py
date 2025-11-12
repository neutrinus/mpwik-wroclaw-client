"""
MPWiK Wrocław e-BOK automation PoC - Playwright version

This script demonstrates how to automate interactions with the MPWiK Wrocław e-BOK
(electronic customer service) using Playwright to retrieve water consumption data.

It is an alternative to the Selenium-based client, often proving to be faster and more reliable.

The process includes:
1. Launching a browser.
2. Navigating to the login page.
3. Filling in credentials and handling reCAPTCHA by relying on the browser's trusted status.
4. Navigating to the water consumption page to establish a full session context.
5. Using the browser's `fetch` API to directly call the backend API for data.
6. Parsing and returning the data.
"""

import logging
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Literal, Optional
from urllib.parse import quote

from playwright.sync_api import sync_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "https://ebok.mpwik.wroc.pl"
API_BASE_URL = f"{BASE_URL}/frontend-api/v1"


class MPWikPlaywrightClient:
    """A client for interacting with the MPWiK e-BOK using Playwright."""

    def __init__(self, login, password, headless=True, browser_type: Literal['chromium', 'firefox', 'webkit'] = 'chromium'):
        self.login = login
        self.password = password
        self.headless = headless
        self.browser_type = browser_type
        self.playwright = None
        self.browser: Optional[Browser] = None
        self._podmiot_id: Optional[str] = None
        self.session_headers: Dict[str, str] = {}

    def __enter__(self):
        """Initializes the Playwright instance and browser."""
        logger.info("Starting Playwright client...")
        self.playwright = sync_playwright().start()
        browser_launcher = getattr(self.playwright, self.browser_type)
        self.browser = browser_launcher.launch(headless=self.headless)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleans up resources by closing the browser and stopping Playwright."""
        logger.info("Closing Playwright client.")
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def _get_page(self) -> Page:
        """Gets a new browser page, creating a browser if necessary."""
        if not self.browser:
            raise ConnectionError("Browser is not initialized. Please use the client as a context manager.")
        return self.browser.new_page()

    def login_and_establish_session(self):
        """
        Logs into the e-BOK portal and navigates to the necessary page to establish a full API session.
        """
        page = self._get_page()
        try:
            logger.info(f"Navigating to login page at {BASE_URL}/login")
            page.goto(f"{BASE_URL}/login")

            logger.info("Filling login credentials.")
            page.fill('input[name="login"]', self.login)
            page.fill('input[name="password"]', self.password)

            logger.info("Clicking the login button.")
            page.click('button[type="submit"]')

            logger.info("Waiting for successful login and navigation to the main page.")
            page.wait_for_url(f"{BASE_URL}/", timeout=60000)
            logger.info("Login successful. URL is now %s", page.url)

            # The podmiot_id is the account ID, which is the same as the login ID
            self._podmiot_id = self.login

            # Navigate to the water consumption page to establish API session context
            water_consumption_url = f"{BASE_URL}/trust/zuzycie-wody?p={self._podmiot_id}"
            logger.info(f"Navigating to water consumption page to establish session: {water_consumption_url}")
            page.goto(water_consumption_url)
            page.wait_for_load_state('networkidle')
            logger.info("Session established.")

        except PlaywrightTimeoutError:
            logger.error("Timeout during login or session establishment. The page might have a reCAPTCHA challenge that could not be bypassed.")
            raise ConnectionError("Failed to log in. A timeout occurred, possibly due to an unsolved reCAPTCHA.")
        finally:
            page.close()

    def _fetch_api_data(self, url: str) -> Dict[str, Any]:
        """
        Uses the browser's fetch API to make a direct call to the backend API.
        This reuses the browser's authenticated session (cookies, headers).
        """
        page = self._get_page()
        try:
            logger.info(f"Fetching API data from: {url}")
            # Use `page.evaluate` to run JavaScript's fetch in the browser context
            js_script = f"""
            async () => {{
                const response = await fetch('{url}', {{
                    headers: {{
                        'Accept': 'application/json',
                        'Content-Type': 'application/json'
                    }},
                    credentials: 'include'
                }});
                if (!response.ok) {{
                    throw new Error(`HTTP error! status: ${{response.status}}`);
                }}
                return await response.json();
            }}()
            """
            result = page.evaluate(js_script)
            logger.info("API data fetched successfully.")
            return result
        except Exception as e:
            logger.error(f"Failed to fetch API data using browser's fetch: {e}")
            raise
        finally:
            page.close()

    def get_points(self) -> List[Dict[str, Any]]:
        """Retrieves the list of active network points (meters)."""
        if not self._podmiot_id:
            raise ValueError("Must log in and establish session before getting points.")
        url = f"{API_BASE_URL}/podmioty/{self._podmiot_id}/punkty-sieci?status=AKTYWNE"
        response_json = self._fetch_api_data(url)
        return response_json.get('punkty', [])

    def get_readings(
        self,
        point_id: str,
        reading_type: Literal['dobowe', 'godzinowe'],
        date_from: datetime,
        date_to: datetime
    ) -> List[Dict[str, Any]]:
        """
        Retrieves water consumption readings for a specific meter.
        - 'dobowe': Daily readings
        - 'godzinowe': Hourly readings
        """
        if not self._podmiot_id:
            raise ValueError("Must log in and establish session before getting readings.")

        # API expects meter numbers with '/' replaced by '-'
        formatted_point_id = point_id.replace('/', '-')

        # URL-encode the datetime strings, as the API requires it
        start_str = quote(date_from.strftime('%Y-%m-%dT%H:%M:%S'))
        end_str = quote(date_to.strftime('%Y-%m-%dT%H:%M:%S'))

        url = (
            f"{API_BASE_URL}/podmioty/{self._podmiot_id}/punkty-sieci/{formatted_point_id}"
            f"/odczyty/{reading_type}?dataOd={start_str}&dataDo={end_str}"
        )

        response_json = self._fetch_api_data(url)
        return response_json.get('odczyty', [])
