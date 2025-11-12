#!/usr/bin/env python3
"""
MPWiK Wrocław Browser Client
Browser automation client for fetching water consumption data from MPWiK Wrocław e-BOK system.
Uses Selenium to handle reCAPTCHA and extract data directly from the web interface.
"""

import logging
import time
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class MPWiKBrowserClient:
    """Browser automation client for MPWiK Wrocław."""
    
    SITE_URL = "https://ebok.mpwik.wroc.pl"
    BASE_URL = "https://ebok.mpwik.wroc.pl/frontend-api/v1"
    
    def __init__(
        self,
        login: str,
        password: str,
        headless: bool = True,
        log_dir: Optional[str] = None,
        browser: str = "chrome",
        debug: bool = False
    ):
        """
        Initialize the browser-based MPWiK client.
        
        Args:
            login: User login (podmiot ID)
            password: User password
            headless: Run browser in headless mode (default: True)
            log_dir: Directory to save logs, HTML, and screenshots (default: ./logs)
            browser: Browser to use (currently only 'chrome' supported)
            debug: Enable debug mode (saves screenshots, HTML, and network logs) (default: False)
        """
        self.login = login
        self.password = password
        self.headless = headless
        self.browser_type = browser
        self.driver = None
        self.authenticated = False
        self.debug = debug
        
        # Setup logging directory
        if log_dir is None:
            log_dir = os.path.join(os.getcwd(), "logs")
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectory for request logs (only in debug mode)
        if self.debug:
            self.requests_log_dir = self.log_dir / "requests"
            self.requests_log_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Request logs will be saved to: {self.requests_log_dir}")
        else:
            self.requests_log_dir = None
        
        # Create timestamp for this session
        self.session_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Counter for request logging
        self.request_counter = 0
        
        logger.debug(f"Browser client initialized with log directory: {self.log_dir}")
        
        # Configure verbose logging to go to files when debug is enabled
        if self.debug:
            self._configure_debug_logging()
    
    def _configure_debug_logging(self):
        """Configure selenium and urllib3 logging to go to files instead of console."""
        # Create a file handler for verbose library logs
        verbose_log_file = self.log_dir / f"verbose_{self.session_timestamp}.log"
        file_handler = logging.FileHandler(verbose_log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        
        # Configure selenium loggers to use file handler only
        selenium_loggers = [
            'selenium.webdriver.remote.remote_connection',
            'urllib3.connectionpool',
            'WDM',
            'selenium'
        ]
        
        for logger_name in selenium_loggers:
            lib_logger = logging.getLogger(logger_name)
            lib_logger.setLevel(logging.DEBUG)
            # Remove console handlers
            lib_logger.handlers = []
            # Add only file handler
            lib_logger.addHandler(file_handler)
            # Don't propagate to root logger (which has console handler)
            lib_logger.propagate = False
        
        logger.info(f"Verbose library logs will be saved to: {verbose_log_file}")
    
    def _setup_driver(self):
        """Setup and configure the WebDriver."""
        if self.driver is not None:
            logger.warning("Driver already initialized")
            return
        
        try:
            logger.info(f"Setting up {self.browser_type} driver...")
            
            if self.browser_type == "chrome":
                options = Options()
                
                if self.headless:
                    options.add_argument("--headless=new")
                    logger.info("Running in headless mode")
                
                # Essential Chrome options for stability
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--disable-gpu")
                options.add_argument("--window-size=1920,1080")
                
                # User agent to avoid detection
                options.add_argument(
                    "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
                )
                
                # Enable logging
                options.set_capability("goog:loggingPrefs", {"performance": "ALL", "browser": "ALL"})
                
                # Install and setup ChromeDriver
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=options)
                
                # Set implicit wait
                self.driver.implicitly_wait(10)
                
                logger.info("Chrome driver initialized successfully")
            else:
                raise ValueError(f"Unsupported browser: {self.browser_type}")
                
        except WebDriverException as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            raise
    
    def _save_page_source(self, prefix: str = "page"):
        """Save current page HTML to log directory (only in debug mode)."""
        if not self.debug:
            return None
        
        try:
            filename = f"{prefix}_{self.session_timestamp}.html"
            filepath = self.log_dir / filename
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(self.driver.page_source)
            
            logger.debug(f"Page source saved to: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Failed to save page source: {e}")
            return None
    
    def _save_screenshot(self, prefix: str = "screenshot"):
        """Save screenshot to log directory (only in debug mode)."""
        if not self.debug:
            return None
        
        try:
            filename = f"{prefix}_{self.session_timestamp}.png"
            filepath = self.log_dir / filename
            
            self.driver.save_screenshot(str(filepath))
            logger.debug(f"Screenshot saved to: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Failed to save screenshot: {e}")
            return None
    
    def _save_network_logs(self, prefix: str = "network"):
        """Save browser network logs to log directory (only in debug mode)."""
        if not self.debug:
            return None
        
        try:
            filename = f"{prefix}_{self.session_timestamp}.json"
            filepath = self.log_dir / filename
            
            # Get performance logs
            logs = self.driver.get_log("performance")
            
            # Process and filter relevant network events
            network_events = []
            for log_entry in logs:
                try:
                    message = json.loads(log_entry["message"])
                    if "message" in message:
                        msg = message["message"]
                        method = msg.get("method", "")
                        
                        # Filter for network events
                        if method.startswith("Network."):
                            network_events.append({
                                "timestamp": log_entry["timestamp"],
                                "level": log_entry["level"],
                                "method": method,
                                "params": msg.get("params", {})
                            })
                except (json.JSONDecodeError, KeyError) as e:
                    continue
            
            # Save to file
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(network_events, f, indent=2)
            
            logger.debug(f"Network logs saved to: {filepath} ({len(network_events)} events)")
            return filepath
        except Exception as e:
            logger.error(f"Failed to save network logs: {e}")
            return None
    
    def _log_request_headers(self):
        """Log current request headers visible in the browser."""
        try:
            # Execute JavaScript to get some header information
            user_agent = self.driver.execute_script("return navigator.userAgent;")
            logger.debug(f"User-Agent: {user_agent}")
            
            # Log cookies
            cookies = self.driver.get_cookies()
            logger.debug(f"Cookies: {len(cookies)} cookie(s)")
            for cookie in cookies:
                logger.debug(f"  {cookie['name']} = {cookie['value'][:20]}...")
            
        except Exception as e:
            logger.error(f"Failed to log request headers: {e}")
    
    def _save_detailed_network_logs(self, prefix: str = "network"):
        """
        Save detailed network logs with each request/response in a separate file.
        This captures comprehensive information useful for implementing non-selenium approach.
        Only enabled in debug mode.
        """
        if not self.debug:
            return []
        
        try:
            # Get performance logs
            logs = self.driver.get_log("performance")
            
            # Create a mapping of request IDs to their data
            requests_map = {}
            
            for log_entry in logs:
                try:
                    message = json.loads(log_entry["message"])
                    if "message" not in message:
                        continue
                    
                    msg = message["message"]
                    method = msg.get("method", "")
                    params = msg.get("params", {})
                    
                    # Handle Network.requestWillBeSent - captures request details
                    if method == "Network.requestWillBeSent":
                        request_id = params.get("requestId")
                        request = params.get("request", {})
                        
                        if request_id not in requests_map:
                            requests_map[request_id] = {
                                "request_id": request_id,
                                "timestamp": log_entry["timestamp"],
                                "url": request.get("url", ""),
                                "method": request.get("method", ""),
                                "headers": request.get("headers", {}),
                                "post_data": request.get("postData", None),
                                "has_post_data": request.get("hasPostData", False),
                                "initiator": params.get("initiator", {}),
                                "type": params.get("type", ""),
                                "frame_id": params.get("frameId", ""),
                                "response": None
                            }
                    
                    # Handle Network.responseReceived - captures response details
                    elif method == "Network.responseReceived":
                        request_id = params.get("requestId")
                        response = params.get("response", {})
                        
                        if request_id in requests_map:
                            requests_map[request_id]["response"] = {
                                "url": response.get("url", ""),
                                "status": response.get("status", 0),
                                "status_text": response.get("statusText", ""),
                                "headers": response.get("headers", {}),
                                "mime_type": response.get("mimeType", ""),
                                "connection_reused": response.get("connectionReused", False),
                                "connection_id": response.get("connectionId", 0),
                                "remote_ip_address": response.get("remoteIPAddress", ""),
                                "remote_port": response.get("remotePort", 0),
                                "from_disk_cache": response.get("fromDiskCache", False),
                                "from_service_worker": response.get("fromServiceWorker", False),
                                "encoded_data_length": response.get("encodedDataLength", 0),
                                "timing": response.get("timing", {}),
                                "protocol": response.get("protocol", ""),
                                "security_state": response.get("securityState", "")
                            }
                    
                    # Handle Network.loadingFinished - indicates response completed
                    elif method == "Network.loadingFinished":
                        request_id = params.get("requestId")
                        if request_id in requests_map:
                            requests_map[request_id]["loading_finished"] = True
                            requests_map[request_id]["encoded_data_length"] = params.get("encodedDataLength", 0)
                    
                    # Handle Network.loadingFailed - indicates request failed
                    elif method == "Network.loadingFailed":
                        request_id = params.get("requestId")
                        if request_id in requests_map:
                            requests_map[request_id]["loading_failed"] = True
                            requests_map[request_id]["error_text"] = params.get("errorText", "")
                            requests_map[request_id]["canceled"] = params.get("canceled", False)
                    
                    # Handle Network.getResponseBody results (if available)
                    elif method == "Network.getResponseBodyResult":
                        request_id = params.get("requestId")
                        if request_id in requests_map:
                            requests_map[request_id]["response_body"] = params.get("body", "")
                            requests_map[request_id]["base64_encoded"] = params.get("base64Encoded", False)
                
                except (json.JSONDecodeError, KeyError) as e:
                    continue
            
            # Fetch response bodies for completed API requests
            # This is only done for JSON/text responses from the MPWiK API
            for request_id, request_data in list(requests_map.items()):
                url = request_data.get("url", "")
                response = request_data.get("response")
                
                # Only fetch bodies for MPWiK API requests with successful responses
                if (response and 
                    "frontend-api" in url and 
                    response.get("status") == 200 and
                    request_data.get("loading_finished")):
                    
                    mime_type = response.get("mime_type", "")
                    if "json" in mime_type or "text" in mime_type:
                        try:
                            # Use Chrome DevTools Protocol to get response body
                            body_result = self.driver.execute_cdp_cmd("Network.getResponseBody", {
                                "requestId": request_id
                            })
                            if body_result:
                                request_data["response_body"] = body_result.get("body", "")
                                request_data["base64_encoded"] = body_result.get("base64Encoded", False)
                                logger.debug(f"Captured response body for: {url[:80]}")
                        except WebDriverException as e:
                            # This is expected when response body is no longer in Chrome's cache
                            # It commonly happens with the error "No resource with given identifier found"
                            # We can safely ignore this as the response was successful (status 200)
                            error_msg = str(e)
                            if "No resource with given identifier found" in error_msg:
                                logger.debug(f"Response body already cleared from cache for: {url[:80]}")
                            else:
                                logger.debug(f"Could not get response body for {url[:80]}: {error_msg.split(chr(10))[0]}")
                        except Exception as e:
                            logger.debug(f"Could not get response body for {url[:80]}: {str(e).split(chr(10))[0]}")
            
            # Save each request to a separate file
            saved_files = []
            for request_id, request_data in requests_map.items():
                # Only save requests to the MPWiK API or site
                url = request_data.get("url", "")
                if "mpwik.wroc.pl" not in url:
                    continue
                
                self.request_counter += 1
                
                # Create a sanitized filename from the URL
                url_path = url.replace("https://", "").replace("http://", "")
                url_path = url_path.replace("/", "_").replace("?", "_").replace("&", "_")
                url_path = url_path[:100]  # Limit length
                
                filename = f"{self.session_timestamp}_{self.request_counter:04d}_{request_data.get('method', 'GET')}_{url_path}.json"
                filepath = self.requests_log_dir / filename
                
                # Save to file
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(request_data, f, indent=2, ensure_ascii=False)
                
                saved_files.append(filepath)
                
                # Log summary
                method = request_data.get("method", "UNKNOWN")
                status = "N/A"
                if request_data.get("response"):
                    status = request_data["response"].get("status", "N/A")
                
                logger.debug(f"Saved request log: {method} {url[:80]} -> {status}")
            
            logger.debug(f"Saved {len(saved_files)} detailed request logs to: {self.requests_log_dir}")
            return saved_files
            
        except Exception as e:
            logger.error(f"Failed to save detailed network logs: {e}")
            logger.exception("Exception details:")
            return []
    
    def _fill_login_field(self, login_value: str) -> bool:
        """
        Fill the login field with the provided value.
        Note: k-login-field does NOT use shadow DOM.
        
        Args:
            login_value: The login value to enter
            
        Returns:
            True if successful, False otherwise
        """
        script = """
        const loginField = document.querySelector('k-login-field');
        if (!loginField) {
            return 'login_field_not_found';
        }
        
        const input = loginField.querySelector('input.mdc-text-field__input');
        if (!input) {
            return 'input_not_found';
        }
        
        input.removeAttribute('readonly');
        input.removeAttribute('disabled');
        input.value = arguments[0];
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        return 'success';
        """
        
        try:
            result = self.driver.execute_script(script, login_value)
            if result == 'success':
                logger.info("✓ Login entered successfully")
                return True
            else:
                logger.error(f"Failed to enter login - {result}")
                self._save_page_source("login_entry_failed")
                self._save_screenshot("login_entry_failed")
                return False
        except Exception as e:
            logger.error(f"Exception while entering login: {e}")
            self._save_page_source("login_entry_exception")
            self._save_screenshot("login_entry_exception")
            return False
    
    def _fill_password_field(self, password_value: str) -> bool:
        """
        Fill the password field with the provided value.
        Note: k-current-password DOES use nested shadow roots:
        k-current-password > shadowRoot > mwc-textfield > shadowRoot > input
        
        Args:
            password_value: The password value to enter
            
        Returns:
            True if successful, False otherwise
        """
        script = """
        const passwordField = document.querySelector('k-current-password');
        if (!passwordField) {
            return 'password_field_not_found';
        }
        
        if (!passwordField.shadowRoot) {
            return 'password_field_no_shadow_root';
        }
        
        const mwcTextField = passwordField.shadowRoot.querySelector('mwc-textfield');
        if (!mwcTextField) {
            return 'mwc_textfield_not_found';
        }
        
        if (!mwcTextField.shadowRoot) {
            return 'mwc_textfield_no_shadow_root';
        }
        
        const input = mwcTextField.shadowRoot.querySelector('input.mdc-text-field__input');
        if (!input) {
            return 'input_not_found';
        }
        
        input.removeAttribute('readonly');
        input.removeAttribute('disabled');
        input.value = arguments[0];
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        return 'success';
        """
        
        try:
            result = self.driver.execute_script(script, password_value)
            if result == 'success':
                logger.info("✓ Password entered successfully via nested shadow DOM")
                return True
            else:
                logger.error(f"Failed to enter password - {result}")
                self._save_page_source("password_entry_failed")
                self._save_screenshot("password_entry_failed")
                return False
        except Exception as e:
            logger.error(f"Exception while entering password: {e}")
            self._save_page_source("password_entry_exception")
            self._save_screenshot("password_entry_exception")
            return False
    
    def _click_login_button(self) -> bool:
        """
        Click the login button.
        Note: k-button DOES use shadow DOM:
        k-button#login-button > shadowRoot > button#button
        
        Returns:
            True if successful, False otherwise
        """
        script = """
        const loginButton = document.querySelector('k-button#login-button');
        if (!loginButton) {
            return 'login_button_not_found';
        }
        
        if (!loginButton.shadowRoot) {
            return 'login_button_no_shadow_root';
        }
        
        const button = loginButton.shadowRoot.querySelector('button#button');
        if (!button) {
            return 'button_not_found';
        }
        
        button.click();
        return 'success';
        """
        
        try:
            result = self.driver.execute_script(script)
            if result == 'success':
                logger.info("✓ Login button clicked successfully via shadow DOM")
                return True
            else:
                logger.error(f"Failed to click login button - {result}")
                self._save_page_source("login_button_click_failed")
                self._save_screenshot("login_button_click_failed")
                return False
        except Exception as e:
            logger.error(f"Exception while clicking login button: {e}")
            self._save_page_source("login_button_click_exception")
            self._save_screenshot("login_button_click_exception")
            return False
    
    def authenticate(self, max_wait: int = 120) -> bool:
        """
        Authenticate with the MPWiK website using browser automation.
        Allows time for manual reCAPTCHA solving if needed.
        
        Args:
            max_wait: Maximum time to wait for authentication (seconds)
            
        Returns:
            True if authentication successful, False otherwise
        """
        try:
            # Setup driver if not already done
            if self.driver is None:
                self._setup_driver()
            
            logger.info("Navigating to login page...")
            self.driver.get(f"{self.SITE_URL}/login")
            
            # Wait for page to load
            time.sleep(2)
            
            # Save initial page state
            self._save_page_source("login_page_initial")
            self._save_screenshot("login_page_initial")
            self._log_request_headers()
            
            # Save detailed network logs for initial page load
            logger.debug("Saving detailed request/response logs for initial page load...")
            self._save_detailed_network_logs("login_page_initial")
            
            # Handle cookie consent overlay if present
            logger.info("Checking for cookie consent overlay...")
            try:
                # Wait longer for overlay to appear (it may load via JavaScript)
                wait_overlay = WebDriverWait(self.driver, 10)
                
                # Check if k-cookie-consent element exists
                try:
                    cookie_consent = wait_overlay.until(
                        EC.presence_of_element_located((By.TAG_NAME, "k-cookie-consent"))
                    )
                    logger.info("Cookie consent component detected")
                    
                    # Wait a bit for shadow DOM to be ready
                    time.sleep(1)
                    
                    # Use JavaScript to access shadow DOM and click the button
                    try:
                        script = """
                        const cookieConsent = document.querySelector('k-cookie-consent');
                        if (cookieConsent && cookieConsent.shadowRoot) {
                            const overlay = cookieConsent.shadowRoot.querySelector('div.overlay');
                            if (overlay) {
                                const button = cookieConsent.shadowRoot.querySelector('k-button[label="Akceptuj"]');
                                if (button && button.shadowRoot) {
                                    const actualButton = button.shadowRoot.querySelector('button');
                                    if (actualButton) {
                                        actualButton.click();
                                        return 'clicked';
                                    }
                                }
                            }
                        }
                        return 'not_found';
                        """
                        result = self.driver.execute_script(script)
                        
                        if result == 'clicked':
                            logger.info("✓ Cookie button clicked via shadow DOM")
                            
                            # Wait for overlay to disappear
                            try:
                                logger.info("Waiting for overlay to disappear...")
                                # Check if overlay is gone by trying to find it
                                WebDriverWait(self.driver, 10).until(
                                    lambda d: d.execute_script("""
                                        const cc = document.querySelector('k-cookie-consent');
                                        if (!cc || !cc.shadowRoot) return true;
                                        const overlay = cc.shadowRoot.querySelector('div.overlay');
                                        return !overlay || overlay.offsetParent === null;
                                    """)
                                )
                                logger.info("✓ Cookie consent overlay dismissed successfully")
                                self._save_screenshot("after_cookie_consent")
                            except TimeoutException:
                                logger.warning("Overlay still visible after clicking - continuing anyway")
                                self._save_screenshot("overlay_still_visible")
                        else:
                            logger.warning("Cookie button not found in shadow DOM")
                            
                    except Exception as e:
                        logger.warning(f"Failed to click cookie button via shadow DOM: {e}")
                        
                except TimeoutException:
                    logger.info("No cookie consent overlay found")
                    
            except Exception as e:
                logger.warning(f"Could not handle cookie consent: {e}")
            
            # Wait for login form to be visible and interactable
            logger.info("Waiting for login form...")
            wait = WebDriverWait(self.driver, 20)
            
            # The form fields are inside shadow DOM, so we need to use JavaScript to access them
            # Wait for the k-login-field element to be present
            try:
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "k-login-field")))
                logger.info("Found k-login-field component")
            except TimeoutException:
                logger.error("Could not find k-login-field component")
                self._save_page_source("login_field_not_found")
                self._save_screenshot("login_field_not_found")
                return False
            
            # Wait a bit for components to be ready
            time.sleep(2)
            
            logger.info("Entering credentials...")
            
            # Enter login using helper method
            if not self._fill_login_field(self.login):
                return False
            
            time.sleep(0.5)
            
            # Enter password using helper method
            if not self._fill_password_field(self.password):
                return False
            
            time.sleep(0.5)
            
            self._save_screenshot("credentials_entered")
            
            # Check for reCAPTCHA
            try:
                recaptcha_element = self.driver.find_element(By.CLASS_NAME, "g-recaptcha")
                logger.warning("reCAPTCHA detected on page")
                logger.info("If running in non-headless mode, please solve the reCAPTCHA manually")
            except NoSuchElementException:
                logger.info("No visible reCAPTCHA element found")
            
            # Wait for k-button element to be present
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "k-button#login-button")))
                logger.info("Found k-button#login-button component")
            except TimeoutException:
                logger.error("Could not find k-button#login-button component")
                self._save_page_source("login_button_not_found")
                self._save_screenshot("login_button_not_found")
                return False
            
            time.sleep(0.5)
            
            # Click login button using helper method
            if not self._click_login_button():
                return False
            
            # Give the browser a moment to send the POST request before navigation
            logger.debug("Waiting for login POST request to be sent...")
            time.sleep(2)
            
            # Save detailed network logs immediately after login attempt
            # This captures the POST /login request before navigation clears the logs
            logger.debug("Saving detailed request/response logs for login attempt...")
            self._save_detailed_network_logs("login_attempt")
            
            # Wait for navigation after login
            logger.info(f"Waiting for authentication (max {max_wait} seconds)...")
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                # Check if we're on a different page (successful login)
                current_url = self.driver.current_url
                logger.debug(f"Current URL: {current_url}")
                
                # Success indicators
                if "/login" not in current_url or "dashboard" in current_url or "podmioty" in current_url:
                    logger.info("Navigation detected - checking authentication status...")
                    self._save_page_source("post_login")
                    self._save_screenshot("post_login")
                    self._save_network_logs("post_login")
                    
                    # Save detailed network logs for each request
                    logger.debug("Saving detailed request/response logs...")
                    self._save_detailed_network_logs("post_login")
                    
                    # Check for error messages
                    try:
                        error_element = self.driver.find_element(By.CSS_SELECTOR, ".error, .alert-danger, [class*='error']")
                        error_text = error_element.text
                        logger.error(f"Login error detected: {error_text}")
                        self._save_screenshot("login_error")
                        return False
                    except NoSuchElementException:
                        # No error found - likely successful
                        logger.info("Authentication successful!")
                        self.authenticated = True
                        return True
                
                # Check for error messages on login page
                try:
                    error_element = self.driver.find_element(By.CSS_SELECTOR, ".error, .alert-danger, [class*='error']")
                    error_text = error_element.text
                    if error_text:
                        logger.error(f"Login error: {error_text}")
                        self._save_page_source("login_error")
                        self._save_screenshot("login_error")
                        return False
                except NoSuchElementException:
                    pass
                
                time.sleep(2)
            
            # Timeout
            logger.error(f"Authentication timeout after {max_wait} seconds")
            self._save_page_source("login_timeout")
            self._save_screenshot("login_timeout")
            return False
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            logger.exception("Full exception details:")
            try:
                self._save_page_source("login_exception")
                self._save_screenshot("login_exception")
            except:
                pass
            return False
    
    def get_readings_from_api(
        self,
        podmiot_id: str,
        punkt_sieci: str,
        date_from: datetime,
        date_to: datetime,
        reading_type: str = "daily"
    ) -> Optional[List[Dict]]:
        """
        Fetch readings by intercepting API calls through the browser.
        
        Args:
            podmiot_id: Entity ID
            punkt_sieci: Network point ID
            date_from: Start date
            date_to: End date
            reading_type: Type of readings ("daily" or "hourly")
            
        Returns:
            List of readings or None if failed
        """
        if not self.authenticated:
            logger.error("Not authenticated. Call authenticate() first.")
            return None
        
        try:
            from urllib.parse import quote
            import time
            
            # Navigate to water consumption page if not already there
            # This sets up X-AccountId, X-Nav-Id, X-SessionId headers needed for API calls
            current_url = self.driver.current_url
            consumption_page_url = f"{self.SITE_URL}/trust/zuzycie-wody?p={podmiot_id}"
            
            if "zuzycie-wody" not in current_url or f"p={podmiot_id}" not in current_url:
                logger.debug(f"Navigating to water consumption page: {consumption_page_url}")
                self.driver.get(consumption_page_url)
                
                # Wait for page to load and session to be established
                # Give it more time to ensure all session headers are set
                time.sleep(3)
                logger.debug(f"Page loaded, current URL: {self.driver.current_url}")
            else:
                logger.debug(f"Already on water consumption page: {current_url}")
            
            # Construct API URL with properly encoded parameters
            endpoint = "dobowe" if reading_type == "daily" else "godzinowe"
            date_from_str = date_from.strftime('%Y-%m-%dT%H:%M:%S')
            date_to_str = date_to.strftime('%Y-%m-%dT%H:%M:%S')
            
            # URL encode the datetime parameters (colons become %3A)
            api_url = (
                f"{self.BASE_URL}/podmioty/{podmiot_id}/punkty-sieci/{punkt_sieci}"
                f"/odczyty/{endpoint}?dataOd={quote(date_from_str)}"
                f"&dataDo={quote(date_to_str)}"
            )
            
            logger.info(f"Fetching {reading_type} readings via browser...")
            logger.info(f"API URL: {api_url}")
            
            # Use JavaScript fetch API to get JSON directly instead of navigating
            # This avoids Chrome's JSON viewer HTML wrapper
            # The fetch will automatically include session cookies and headers set by the page
            # Enhanced error handling to capture response details
            result = self.driver.execute_async_script("""
                const callback = arguments[arguments.length - 1];
                const url = arguments[0];
                
                console.log('[FETCH] Calling API:', url);
                
                fetch(url, {
                    method: 'GET',
                    credentials: 'include',
                    headers: {
                        'Accept': 'application/json',
                        'Content-Type': 'application/json'
                    }
                })
                .then(response => {
                    console.log('[FETCH] Response status:', response.status);
                    console.log('[FETCH] Response headers:', response.headers);
                    
                    if (!response.ok) {
                        // Try to get error response body
                        return response.text().then(text => {
                            console.error('[FETCH] Error response body:', text);
                            throw new Error('HTTP error ' + response.status + ': ' + text);
                        });
                    }
                    return response.json();
                })
                .then(data => {
                    console.log('[FETCH] Success, data received');
                    callback({ success: true, data: data });
                })
                .catch(error => {
                    console.error('[FETCH] Error:', error);
                    callback({ success: false, error: error.message });
                });
            """, api_url)
            
            # Log browser console output for debugging
            try:
                browser_logs = self.driver.get_log('browser')
                if browser_logs:
                    logger.debug("Browser console logs:")
                    for log_entry in browser_logs[-10:]:  # Last 10 entries
                        logger.debug(f"  [{log_entry['level']}] {log_entry['message']}")
            except Exception as e:
                logger.debug(f"Could not retrieve browser logs: {e}")
            
            # Save detailed network logs for this API call (including failed requests)
            try:
                logger.debug(f"Saving detailed request/response logs for {reading_type} API call...")
                self._save_detailed_network_logs(f"api_{reading_type}")
            except Exception as e:
                logger.debug(f"Could not save detailed network logs: {e}")
            
            if result.get('success'):
                data = result.get('data', {})
                
                # Extract readings
                readings = data.get("odczyty", [])
                logger.info(f"Retrieved {len(readings)} {reading_type} readings")
                
                # Save the readings to a file (debug mode only)
                if self.debug:
                    readings_file = self.log_dir / f"readings_{reading_type}_{self.session_timestamp}.json"
                    with open(readings_file, "w", encoding="utf-8") as f:
                        json.dump(readings, f, indent=2, ensure_ascii=False)
                    logger.info(f"Readings saved to: {readings_file}")
                
                return readings
            else:
                error = result.get('error', 'Unknown error')
                logger.error(f"Failed to fetch readings via JavaScript: {error}")
                
                # Log more details about the failure
                logger.error(f"Request URL was: {api_url}")
                logger.error(f"Current browser URL: {self.driver.current_url}")
                
                return None
                
        except Exception as e:
            logger.error(f"Failed to fetch readings: {e}")
            logger.exception("Full exception details:")
            try:
                self._save_page_source(f"readings_error_{reading_type}")
                self._save_screenshot(f"readings_error_{reading_type}")
            except:
                pass
            return None
    
    def get_punkty_sieci(
        self,
        podmiot_id: str,
        status: str = "AKTYWNE"
    ) -> Optional[List[Dict]]:
        """
        Fetch list of network points (meters) by accessing API through the browser.
        
        Args:
            podmiot_id: Entity ID (podmiot)
            status: Filter by status (default: "AKTYWNE" for active meters)
            
        Returns:
            List of network points or None if failed
        """
        if not self.authenticated:
            logger.error("Not authenticated. Call authenticate() first.")
            return None
        
        try:
            import time
            
            # Navigate to a page that establishes session context (if not already there)
            # This ensures session headers are properly set for API calls
            current_url = self.driver.current_url
            if "zuzycie-wody" not in current_url and "trust" not in current_url:
                consumption_page_url = f"{self.SITE_URL}/trust/zuzycie-wody?p={podmiot_id}"
                logger.debug(f"Navigating to water consumption page: {consumption_page_url}")
                self.driver.get(consumption_page_url)
                time.sleep(2)
            
            # Construct API URL
            api_url = f"{self.BASE_URL}/podmioty/{podmiot_id}/punkty-sieci?status={status}"
            
            logger.info(f"Fetching network points for podmiot {podmiot_id} via browser...")
            logger.debug(f"API URL: {api_url}")
            
            # Use JavaScript fetch API to get JSON directly instead of navigating
            # This avoids Chrome's JSON viewer HTML wrapper
            result = self.driver.execute_async_script("""
                const callback = arguments[arguments.length - 1];
                const url = arguments[0];
                fetch(url, {
                    method: 'GET',
                    credentials: 'include',
                    headers: {
                        'Accept': 'application/json',
                        'Content-Type': 'application/json'
                    }
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('HTTP error ' + response.status);
                    }
                    return response.json();
                })
                .then(data => {
                    callback({ success: true, data: data });
                })
                .catch(error => {
                    callback({ success: false, error: error.message });
                });
            """, api_url)
            
            if result.get('success'):
                data = result.get('data', {})
                
                # Extract punkty
                punkty = data.get("punkty", [])
                logger.info(f"Retrieved {len(punkty)} network points")
                
                # Save the punkty to a file (debug mode only)
                if self.debug:
                    punkty_file = self.log_dir / f"punkty_sieci_{self.session_timestamp}.json"
                    with open(punkty_file, "w", encoding="utf-8") as f:
                        json.dump(punkty, f, indent=2, ensure_ascii=False)
                    logger.info(f"Network points saved to: {punkty_file}")
                
                return punkty
            else:
                error = result.get('error', 'Unknown error')
                logger.error(f"Failed to fetch network points via JavaScript: {error}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to fetch network points: {e}")
            logger.exception("Full exception details:")
            try:
                self._save_page_source(f"punkty_sieci_error")
                self._save_screenshot(f"punkty_sieci_error")
            except:
                pass
            return None
    
    def get_daily_readings(
        self,
        podmiot_id: str,
        punkt_sieci: str,
        date_from: datetime,
        date_to: datetime
    ) -> Optional[List[Dict]]:
        """Fetch daily water consumption readings."""
        return self.get_readings_from_api(
            podmiot_id, punkt_sieci, date_from, date_to, "daily"
        )
    
    def get_hourly_readings(
        self,
        podmiot_id: str,
        punkt_sieci: str,
        date_from: datetime,
        date_to: datetime
    ) -> Optional[List[Dict]]:
        """Fetch hourly water consumption readings."""
        return self.get_readings_from_api(
            podmiot_id, punkt_sieci, date_from, date_to, "hourly"
        )
    
    def close(self):
        """Close the browser and cleanup."""
        if self.driver is not None:
            try:
                logger.info("Closing browser...")
                self.driver.quit()
                self.driver = None
                self.authenticated = False
            except Exception as e:
                logger.error(f"Error closing browser: {e}")
    
    def print_readings(self, readings: List[Dict], reading_type: str = "daily"):
        """
        Print readings in a formatted way.
        
        Args:
            readings: List of reading dictionaries
            reading_type: Type of readings ("daily" or "hourly")
        """
        if not readings:
            logger.warning("No readings to display")
            return
        
        print(f"\n{'='*80}")
        print(f"{reading_type.upper()} WATER CONSUMPTION READINGS")
        print(f"{'='*80}")
        print(f"{'Date/Time':<20} {'Meter':<15} {'Reading (m³)':<15} {'Usage (m³)':<15} {'Type':<10}")
        print(f"{'-'*80}")
        
        for reading in readings:
            date_str = reading.get('data', 'N/A')
            meter = reading.get('licznik', 'N/A')
            wskazanie = reading.get('wskazanie', 0.0)
            zuzycie = reading.get('zuzycie', 0.0)
            typ = reading.get('typ', 'N/A')
            
            print(f"{date_str:<20} {meter:<15} {wskazanie:<15.3f} {zuzycie:<15.3f} {typ:<10}")
        
        # Calculate totals
        total_usage = sum(r.get('zuzycie', 0.0) for r in readings)
        print(f"{'-'*80}")
        print(f"Total usage: {total_usage:.3f} m³")
        print(f"{'='*80}\n")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False


def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Fetch water consumption data from MPWiK Wrocław using browser automation'
    )
    parser.add_argument('--login', required=True, help='Login (podmiot ID)')
    parser.add_argument('--password', required=True, help='Password')
    parser.add_argument('--podmiot-id', required=True, help='Podmiot ID')
    parser.add_argument('--punkt-sieci', required=True, help='Network point ID')
    parser.add_argument(
        '--type',
        choices=['daily', 'hourly', 'both'],
        default='hourly',
        help='Type of readings to fetch (default: hourly)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=0,
        help='Number of days to fetch (default: 0 for today only)'
    )
    parser.add_argument(
        '--date-from',
        help='Start date (YYYY-MM-DD), defaults to N days ago'
    )
    parser.add_argument(
        '--date-to',
        help='End date (YYYY-MM-DD), defaults to today'
    )
    parser.add_argument(
        '--output',
        help='Output file path (JSON format)'
    )
    parser.add_argument(
        '--headless',
        action='store_true',
        default=True,
        help='Run browser in headless mode (default: True)'
    )
    parser.add_argument(
        '--no-headless',
        action='store_true',
        help='Run browser with visible window (for manual reCAPTCHA solving)'
    )
    parser.add_argument(
        '--log-dir',
        help='Directory to save logs and screenshots (default: ./logs)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    # Determine headless mode
    headless = args.headless and not args.no_headless
    if args.no_headless:
        logger.info("Running in non-headless mode (visible browser window)")
    
    # Parse dates
    if args.date_to:
        date_to = datetime.strptime(args.date_to, '%Y-%m-%d').replace(
            hour=23, minute=59, second=59
        )
    else:
        date_to = datetime.now().replace(hour=23, minute=59, second=59)
    
    if args.date_from:
        date_from = datetime.strptime(args.date_from, '%Y-%m-%d').replace(
            hour=0, minute=0, second=0
        )
    else:
        date_from = (date_to - timedelta(days=args.days)).replace(
            hour=0, minute=0, second=0
        )
    
    # Create client
    with MPWiKBrowserClient(
        login=args.login,
        password=args.password,
        headless=headless,
        log_dir=args.log_dir,
        debug=args.debug
    ) as client:
        
        # Authenticate
        if not client.authenticate():
            logger.error("Authentication failed. Check logs for details.")
            return 1
        
        results = {}
        
        # Fetch daily readings
        if args.type in ['daily', 'both']:
            daily_readings = client.get_daily_readings(
                args.podmiot_id,
                args.punkt_sieci,
                date_from,
                date_to
            )
            
            if daily_readings:
                results['daily'] = daily_readings
                client.print_readings(daily_readings, "daily")
        
        # Fetch hourly readings
        if args.type in ['hourly', 'both']:
            # For hourly, limit to smaller time ranges
            if args.type == 'hourly':
                hourly_date_from = date_from
                hourly_date_to = date_to
            else:
                # If fetching both, only get hourly for last day
                hourly_date_from = date_to.replace(hour=0, minute=0, second=0)
                hourly_date_to = date_to
            
            hourly_readings = client.get_hourly_readings(
                args.podmiot_id,
                args.punkt_sieci,
                hourly_date_from,
                hourly_date_to
            )
            
            if hourly_readings:
                results['hourly'] = hourly_readings
                client.print_readings(hourly_readings, "hourly")
        
        # Save to file if requested
        if args.output:
            try:
                with open(args.output, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)
                logger.info(f"Results saved to {args.output}")
            except Exception as e:
                logger.error(f"Failed to save results: {e}")
        
        if args.debug:
            logger.info(f"Debug files (logs, screenshots, and network data) saved to: {client.log_dir}")
        
    return 0


if __name__ == '__main__':
    exit(main())
