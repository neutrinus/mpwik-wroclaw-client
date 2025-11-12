#!/usr/bin/env python3
"""
MPWiK Wrocław Direct API Client
Client for fetching water consumption data from MPWiK Wrocław e-BOK system using direct API calls.
"""

import requests
import logging
import re
import time
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class MPWiKClient:
    """Client for MPWiK Wrocław API."""
    
    BASE_URL = "https://ebok.mpwik.wroc.pl/frontend-api/v1"
    SITE_URL = "https://ebok.mpwik.wroc.pl"
    
    def __init__(self, login: str, password: str, recaptcha_api_key: Optional[str] = None, 
                 recaptcha_version: Optional[int] = None, debug: bool = False, log_dir: Optional[str] = None):
        """
        Initialize the MPWiK client.
        
        Args:
            login: User login (podmiot ID)
            password: User password
            recaptcha_api_key: Optional API key for ReCAPTCHA solving service (e.g., CapMonster)
            recaptcha_version: Optional preferred ReCAPTCHA version (2 or 3). If None, tries v3 first then v2.
            debug: Enable debug mode (saves request/response logs to files)
            log_dir: Directory to save logs (default: ./logs)
        """
        self.login = login
        self.password = password
        self.recaptcha_api_key = recaptcha_api_key
        self.recaptcha_version = recaptcha_version
        self.debug = debug
        self.log_dir = log_dir or "./logs"
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
            'Origin': self.SITE_URL,
            'Referer': f'{self.SITE_URL}/login',
            'DNT': '1',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        })
        self.token = None
        self.csrf_token = None
        self.recaptcha_token = None
    
    def _save_request_log(self, request_type: str, url: str, method: str, 
                          headers: dict, payload: Optional[dict], response: Optional[requests.Response]):
        """
        Save request and response details to a JSON file for debugging.
        Only saves when debug mode is enabled.
        
        Args:
            request_type: Type of request (e.g., "login", "daily_readings")
            url: Request URL
            method: HTTP method
            headers: Request headers
            payload: Request payload (will be sanitized)
            response: Response object
        """
        if not self.debug:
            return
        
        try:
            # Create log directory if it doesn't exist
            log_dir = Path(self.log_dir) / "requests"
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Sanitize URL for filename
            url_part = url.replace("https://", "").replace("http://", "").replace("/", "_")
            filename = f"{timestamp}_{method}_{url_part}_{request_type}.json"
            filepath = log_dir / filename
            
            # Sanitize payload (remove password)
            sanitized_payload = None
            if payload:
                sanitized_payload = payload.copy()
                if 'password' in sanitized_payload:
                    sanitized_payload['password'] = '***'
            
            # Build log data
            log_data = {
                "timestamp": timestamp,
                "request_type": request_type,
                "url": url,
                "method": method,
                "headers": dict(headers),
                "payload": sanitized_payload
            }
            
            # Add response data if available
            if response is not None:
                log_data["response"] = {
                    "status_code": response.status_code,
                    "status_text": response.reason,
                    "headers": dict(response.headers),
                    "elapsed_ms": response.elapsed.total_seconds() * 1000
                }
                
                # Try to add response body (if JSON)
                try:
                    log_data["response"]["body"] = response.json()
                except:
                    log_data["response"]["body_text"] = response.text[:500] if response.text else None
            
            # Write to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Request log saved to: {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to save request log: {e}")
    
    def solve_recaptcha(self, site_key: str, recaptcha_version: int = 3) -> Optional[str]:
        """
        Solve ReCAPTCHA using CapMonster Cloud service.
        Uses the official CapMonster Python client library.
        
        Args:
            site_key: ReCAPTCHA site key from the website
            recaptcha_version: ReCAPTCHA version (2 or 3), defaults to 3
            
        Returns:
            ReCAPTCHA token if successful, None otherwise
        """
        if not self.recaptcha_api_key:
            logger.debug("No ReCAPTCHA API key provided, skipping ReCAPTCHA solving")
            return None
        
        if not site_key:
            logger.error("No ReCAPTCHA site key provided")
            return None
        
        try:
            # Import CapMonster client library
            try:
                import asyncio
                from capmonstercloudclient import CapMonsterClient, ClientOptions
                from capmonstercloudclient.requests import RecaptchaV3ProxylessRequest, RecaptchaV2Request
            except ImportError:
                import sys
                python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
                logger.warning(f"CapMonster client library not installed. Install with: uv sync --extra capmonster")
                if sys.version_info >= (3, 14):
                    logger.warning(f"Note: capmonstercloudclient may not support Python {python_version} yet. Consider using Python 3.10-3.13")
                logger.info("Falling back to direct API calls...")
                return self._solve_recaptcha_direct(site_key, recaptcha_version)
            
            logger.info(f"Attempting to solve ReCAPTCHA v{recaptcha_version} using CapMonster client...")
            logger.info(f"ReCAPTCHA site key: {site_key}")
            logger.debug(f"Target URL: {self.SITE_URL}/login")
            
            # Get the User-Agent from session headers
            # This is critical: CapMonster must use the same User-Agent that will be used
            # in the actual login request to avoid token validation failures
            user_agent = self.session.headers.get('User-Agent', 
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36')
            logger.debug(f"Using User-Agent for CapMonster: {user_agent}")
            
            # Create CapMonster client
            client_options = ClientOptions(api_key=self.recaptcha_api_key)
            cap_monster_client = CapMonsterClient(options=client_options)
            
            # Create request based on version
            if recaptcha_version == 3:
                # Note: RecaptchaV3ProxylessRequest in the current client version doesn't support userAgent parameter
                # For best results, we use direct API call which supports userAgent
                logger.debug("Using direct API call for v3 to pass userAgent parameter")
                return self._solve_recaptcha_direct(site_key, recaptcha_version)
            else:
                # ReCAPTCHA v2 - supports userAgent parameter
                recaptcha_request = RecaptchaV2Request(
                    websiteUrl=f"{self.SITE_URL}/login",
                    websiteKey=site_key,
                    userAgent=user_agent  # Pass User-Agent to match login request
                )
                
                logger.debug("Solving ReCAPTCHA v2 with CapMonster client...")
                
                # Solve captcha asynchronously
                async def solve():
                    return await cap_monster_client.solve_captcha(recaptcha_request)
                
                response = asyncio.run(solve())
                
                if response and 'gRecaptchaResponse' in response:
                    token = response['gRecaptchaResponse']
                    logger.info("ReCAPTCHA solved successfully")
                    logger.debug(f"Token length: {len(token)} characters")
                    return token
                else:
                    logger.error(f"Unexpected response from CapMonster: {response}")
                    return None
            
        except Exception as e:
            logger.error(f"Failed to solve ReCAPTCHA with client library: {e}")
            logger.exception("Full exception details:")
            logger.info("Falling back to direct API calls...")
            return self._solve_recaptcha_direct(site_key, recaptcha_version)
    
    def _solve_recaptcha_direct(self, site_key: str, recaptcha_version: int = 3) -> Optional[str]:
        """
        Solve ReCAPTCHA using direct API calls (fallback method).
        This method is used when the client library is not available or doesn't support required features.
        
        Args:
            site_key: ReCAPTCHA site key from the website
            recaptcha_version: ReCAPTCHA version (2 or 3), defaults to 3
            
        Returns:
            ReCAPTCHA token if successful, None otherwise
        """
        try:
            logger.debug("Using direct API calls to CapMonster")
            
            # Get the User-Agent from session headers
            user_agent = self.session.headers.get('User-Agent', 
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36')
            
            # CapMonster API endpoint
            capmonster_url = "https://api.capmonster.cloud/createTask"
            
            # Create task based on version
            if recaptcha_version == 3:
                task_payload = {
                    "clientKey": self.recaptcha_api_key,
                    "task": {
                        "type": "RecaptchaV3TaskProxyless",
                        "websiteURL": f"{self.SITE_URL}/login",
                        "websiteKey": site_key,
                        "minScore": 0.7,
                        "pageAction": "login",
                        "userAgent": user_agent  # Pass User-Agent to match login request
                    }
                }
            else:
                # ReCAPTCHA v2
                task_payload = {
                    "clientKey": self.recaptcha_api_key,
                    "task": {
                        "type": "NoCaptchaTaskProxyless",
                        "websiteURL": f"{self.SITE_URL}/login",
                        "websiteKey": site_key,
                        "userAgent": user_agent  # Pass User-Agent to match login request
                    }
                }
            
            logger.debug(f"Creating ReCAPTCHA task at {capmonster_url}")
            response = requests.post(capmonster_url, json=task_payload)
            response.raise_for_status()
            task_data = response.json()
            
            logger.debug(f"CapMonster createTask response: {task_data}")
            
            if task_data.get("errorId") != 0:
                logger.error(f"CapMonster error: {task_data.get('errorDescription')}")
                logger.error(f"Full response: {task_data}")
                return None
            
            task_id = task_data.get("taskId")
            logger.info(f"ReCAPTCHA task created: {task_id}")
            
            # Poll for result
            result_url = "https://api.capmonster.cloud/getTaskResult"
            max_attempts = 60  # 60 attempts * 2 seconds = 120 seconds (2 minutes)
            
            for attempt in range(max_attempts):
                time.sleep(2)
                
                result_payload = {
                    "clientKey": self.recaptcha_api_key,
                    "taskId": task_id
                }
                
                logger.debug(f"Polling ReCAPTCHA result (attempt {attempt + 1}/{max_attempts})...")
                result_response = requests.post(result_url, json=result_payload)
                result_response.raise_for_status()
                result_data = result_response.json()
                
                status = result_data.get("status")
                logger.info(f"ReCAPTCHA status: {status} (attempt {attempt + 1}/{max_attempts})")
                
                if status == "ready":
                    token = result_data.get("solution", {}).get("gRecaptchaResponse")
                    if token:
                        logger.info("ReCAPTCHA solved successfully")
                        logger.debug(f"Token length: {len(token)} characters")
                        return token
                    else:
                        logger.error("ReCAPTCHA marked as ready but no token in response")
                        logger.error(f"Full response: {result_data}")
                        return None
                elif status == "processing":
                    logger.debug(f"ReCAPTCHA solving in progress...")
                else:
                    logger.error(f"Unexpected ReCAPTCHA status: {status}")
                    logger.error(f"Full response: {result_data}")
                    if result_data.get("errorId"):
                        logger.error(f"Error: {result_data.get('errorDescription')}")
                    return None
            
            logger.error(f"ReCAPTCHA solving timeout after {max_attempts * 2} seconds")
            return None
            
        except Exception as e:
            logger.error(f"Failed to solve ReCAPTCHA with direct API: {e}")
            logger.exception("Full exception details:")
            return None
    
    def _attempt_login(self, recaptcha_token: Optional[str] = None, csrf_token: Optional[str] = None) -> Tuple[bool, Optional[dict], Optional[requests.Response]]:
        """
        Attempt login with optional ReCAPTCHA and CSRF tokens.
        
        Args:
            recaptcha_token: Optional ReCAPTCHA token
            csrf_token: Optional CSRF token
            
        Returns:
            Tuple of (success, response_data, response_object)
        """
        try:
            # Prepare headers for login request
            login_headers = {}
            if csrf_token:
                login_headers['X-CSRF-TOKEN'] = csrf_token
                logger.debug("Using CSRF token for authentication")
            
            # Add ReCAPTCHA token to headers (this is how the browser does it)
            if recaptcha_token:
                login_headers['X-RECAPTCHA-TOKEN'] = recaptcha_token
                logger.info("Using ReCAPTCHA token for authentication (in X-RECAPTCHA-TOKEN header)")
                logger.debug(f"ReCAPTCHA token (first 20 chars): {recaptcha_token[:20]}...")
            
            # Prepare login payload - only login and password (verified from browser logs)
            url = f"{self.BASE_URL}/login"
            payload = {
                "login": self.login,
                "password": self.password
            }
            
            # Log detailed request information
            logger.info("Attempting to authenticate...")
            logger.debug(f"POST {url}")
            logger.debug(f"Payload: {json.dumps({'login': self.login, 'password': '***'})}")
            logger.debug(f"Headers: {list(login_headers.keys())}")
            logger.debug(f"Session cookies: {list(self.session.cookies.keys())}")
            
            # Merge session headers with login-specific headers to ensure all headers are sent
            # This explicitly includes Origin and Referer from session headers
            temp_headers = self.session.headers.copy()
            temp_headers.update(login_headers)
            
            response = self.session.post(url, json=payload, headers=temp_headers)
            
            # Save request/response log if debug mode is enabled
            self._save_request_log("login", url, "POST", temp_headers, payload, response)
            
            # Log response details
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response headers: {dict(response.headers)}")
            
            # Check for successful authentication
            if response.status_code == 200:
                data = response.json()
                logger.debug(f"Login response keys: {list(data.keys())}")
                return True, data, response
            else:
                # Authentication failed
                logger.warning(f"Authentication failed with status {response.status_code}")
                try:
                    error_data = response.json()
                    logger.error(f"Error response: {json.dumps(error_data, indent=2)}")
                except:
                    logger.error(f"Error response (raw): {response.text[:500]}")
                return False, None, response
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request exception during login: {e}")
            return False, None, None
        
    def authenticate(self, max_retries: int = 2) -> bool:
        """
        Authenticate with the MPWiK API.
        
        Args:
            max_retries: Maximum number of retry attempts if authentication fails (default: 2)
        
        Returns:
            True if authentication successful, False otherwise
        """
        try:
            # Step 1: Visit the login page to get cookies and CSRF token
            logger.info("Fetching login page to get CSRF token...")
            login_page_url = f"{self.SITE_URL}/login"
            logger.debug(f"GET {login_page_url}")
            page_response = self.session.get(login_page_url)
            page_response.raise_for_status()
            
            # Save request/response log for initial GET if debug mode is enabled
            self._save_request_log("get_login_page", login_page_url, "GET", self.session.headers, None, page_response)
            
            logger.debug(f"Login page response status: {page_response.status_code}")
            logger.debug(f"Cookies received: {list(self.session.cookies.keys())}")
            
            # Step 1.5: Call session/info endpoint to get CSRF token (matches browser behavior)
            # The browser JavaScript calls this endpoint before login to retrieve the CSRF token
            logger.info("Fetching session info to get CSRF token...")
            session_info_url = f"{self.BASE_URL}/session/info"
            logger.debug(f"GET {session_info_url}")
            session_response = self.session.get(session_info_url)
            
            # Save request/response log if debug mode is enabled
            self._save_request_log("get_session_info", session_info_url, "GET", self.session.headers, None, session_response)
            
            # Try to extract CSRF token from session/info response
            csrf_token = None
            if session_response.status_code == 200:
                try:
                    session_data = session_response.json()
                    csrf_token = session_data.get('csrfToken')
                    if csrf_token:
                        logger.info("Found CSRF token in session/info response")
                        logger.debug(f"CSRF token: {csrf_token[:20]}...")
                    else:
                        logger.debug("No CSRF token in session/info response, will try other sources")
                except Exception as e:
                    logger.debug(f"Could not parse session/info response: {e}")
            else:
                logger.debug(f"Session info request failed with status {session_response.status_code}")
            
            # If no CSRF token from session/info, try to extract from HTML or cookies
            # The token might be in a meta tag or script in the HTML
            if not csrf_token:
                # Check if CSRF token is in cookies
                logger.debug("Searching for CSRF token in cookies...")
                for cookie in self.session.cookies:
                    logger.debug(f"Cookie: {cookie.name} = {cookie.value[:20]}..." if len(cookie.value) > 20 else f"Cookie: {cookie.name} = {cookie.value}")
                    if 'csrf' in cookie.name.lower() or 'xsrf' in cookie.name.lower():
                        csrf_token = cookie.value
                        logger.info(f"Found CSRF token in cookie: {cookie.name}")
                        break
            
            # If no CSRF token found in cookies, try to parse from HTML
            if not csrf_token:
                logger.debug("No CSRF token in cookies, searching in HTML...")
                # Look for common CSRF token patterns in HTML
                csrf_patterns = [
                    r'<meta[^>]*name=["\']csrf["\'][^>]*content=["\']([^"\']+)["\']',  # MPWiK specific: name="csrf"
                    r'<meta[^>]*name=["\']csrf-token["\'][^>]*content=["\']([^"\']+)["\']',
                    r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*name=["\']csrf-token["\']',
                    r'csrf["\']?\s*:\s*["\']([^"\']+)["\']',
                    r'X-CSRF-TOKEN["\']?\s*:\s*["\']([^"\']+)["\']'
                ]
                
                for i, pattern in enumerate(csrf_patterns):
                    match = re.search(pattern, page_response.text, re.IGNORECASE)
                    if match:
                        csrf_token = match.group(1)
                        logger.info(f"Found CSRF token in HTML (pattern {i+1})")
                        logger.debug(f"CSRF token: {csrf_token[:20]}...")
                        break
                
                if not csrf_token:
                    logger.debug(f"HTML page length: {len(page_response.text)} characters")
                    logger.debug(f"First 500 chars of HTML: {page_response.text[:500]}")
            
            if csrf_token:
                self.csrf_token = csrf_token
            else:
                logger.warning("No CSRF token found, attempting login without it")
            
            # Step 2: Extract ReCAPTCHA site key from the page
            recaptcha_site_key = None
            if self.recaptcha_api_key:
                logger.info("Searching for ReCAPTCHA site key in login page...")
                # Common patterns for ReCAPTCHA site key
                sitekey_patterns = [
                    r'<meta\s+name=["\']recaptcha\.site\.key["\']\s+content=["\']([^"\']+)["\']',  # MPWiK specific
                    r'data-sitekey=["\']([^"\']+)["\']',
                    r'sitekey["\']?\s*:\s*["\']([^"\']+)["\']',
                    r'grecaptcha\.execute\(["\']([^"\']+)["\']',
                    r'render["\']?\s*:\s*["\']([^"\']+)["\']'
                ]
                
                for i, pattern in enumerate(sitekey_patterns):
                    match = re.search(pattern, page_response.text, re.IGNORECASE)
                    if match:
                        recaptcha_site_key = match.group(1)
                        logger.info(f"Found ReCAPTCHA site key (pattern {i+1}): {recaptcha_site_key}")
                        break
                
                if not recaptcha_site_key:
                    logger.warning("Could not find ReCAPTCHA site key in HTML")
                    logger.debug("Searching for 'recaptcha' in HTML...")
                    if 'recaptcha' in page_response.text.lower():
                        logger.debug("Found 'recaptcha' string in HTML, but couldn't extract site key")
                        # Try to find any 6L string that looks like a site key
                        generic_match = re.search(r'6[A-Za-z0-9_-]{39}', page_response.text)
                        if generic_match:
                            recaptcha_site_key = generic_match.group(0)
                            logger.info(f"Found potential ReCAPTCHA site key using generic pattern: {recaptcha_site_key}")
                    else:
                        logger.debug("No 'recaptcha' string found in HTML")
                        logger.info("ReCAPTCHA may not be required for this login attempt")
            
            # Step 3: Solve ReCAPTCHA if API key provided and site key found
            recaptcha_token = None
            if self.recaptcha_api_key and recaptcha_site_key:
                # Determine which version to use
                if self.recaptcha_version is not None:
                    # Use user-specified version
                    logger.info(f"Using user-specified ReCAPTCHA v{self.recaptcha_version}...")
                    recaptcha_token = self.solve_recaptcha(recaptcha_site_key, recaptcha_version=self.recaptcha_version)
                else:
                    # Try v3 first (invisible ReCAPTCHA) - this site typically uses v3
                    logger.info("Attempting ReCAPTCHA v3 (invisible)...")
                    recaptcha_token = self.solve_recaptcha(recaptcha_site_key, recaptcha_version=3)
                    
                    # If v3 fails, try v2 as fallback
                    if not recaptcha_token:
                        logger.info("ReCAPTCHA v3 failed, trying v2 (checkbox) as fallback...")
                        recaptcha_token = self.solve_recaptcha(recaptcha_site_key, recaptcha_version=2)
                
                if recaptcha_token:
                    self.recaptcha_token = recaptcha_token
                    logger.info("ReCAPTCHA token obtained successfully")
                    logger.debug(f"ReCAPTCHA token length: {len(recaptcha_token)}")
                else:
                    logger.warning("Failed to obtain ReCAPTCHA token")
            elif self.recaptcha_api_key and not recaptcha_site_key:
                logger.warning("ReCAPTCHA API key provided but site key not found - will attempt login without ReCAPTCHA")
            else:
                logger.info("No ReCAPTCHA API key provided - will attempt login without ReCAPTCHA")
            
            # Step 4: Attempt login with retry mechanism
            for attempt in range(max_retries + 1):
                if attempt > 0:
                    logger.info(f"Retry attempt {attempt}/{max_retries}...")
                    
                    # Get fresh ReCAPTCHA token for retry
                    if self.recaptcha_api_key and recaptcha_site_key:
                        logger.info("Obtaining fresh ReCAPTCHA token for retry...")
                        if self.recaptcha_version is not None:
                            recaptcha_token = self.solve_recaptcha(recaptcha_site_key, recaptcha_version=self.recaptcha_version)
                        else:
                            recaptcha_token = self.solve_recaptcha(recaptcha_site_key, recaptcha_version=3)
                        
                        if recaptcha_token:
                            self.recaptcha_token = recaptcha_token
                            logger.info("Fresh ReCAPTCHA token obtained for retry")
                        else:
                            logger.error("Failed to obtain fresh ReCAPTCHA token for retry")
                
                success, data, response = self._attempt_login(recaptcha_token, csrf_token)
                
                if success:
                    # Store authentication token if present in response
                    if 'token' in data:
                        self.token = data['token']
                        self.session.headers.update({
                            'Authorization': f'Bearer {self.token}'
                        })
                        logger.info("Authentication token received and stored")
                    
                    logger.info("Authentication successful")
                    return True
                else:
                    # Check if it's a ReCAPTCHA-related error
                    if response is not None:
                        if response.status_code == 401:
                            try:
                                error_data = response.json()
                                error_msg = str(error_data).upper()
                                if 'RECAPTCHA' in error_msg or 'CAPTCHA' in error_msg:
                                    logger.error("Authentication failed: ReCAPTCHA validation error")
                                    logger.error("Possible causes:")
                                    logger.error("  1. ReCAPTCHA token expired (tokens are time-sensitive)")
                                    logger.error("  2. ReCAPTCHA score too low (try with higher minScore)")
                                    logger.error("  3. ReCAPTCHA token rejected by server")
                                    logger.error("  4. Wrong ReCAPTCHA version (try v2 if v3 fails)")
                                    if attempt < max_retries:
                                        logger.info("Will retry with a fresh token...")
                                        continue
                            except:
                                pass
                        elif response.status_code == 403:
                            logger.error("Authentication failed: Access forbidden (403)")
                            logger.error("This may indicate:")
                            logger.error("  1. ReCAPTCHA is required but not provided or invalid")
                            logger.error("  2. IP address blocked or rate limited")
                            logger.error("  3. Invalid credentials")
                            if self.recaptcha_api_key:
                                if attempt < max_retries:
                                    logger.info("Will retry with a fresh token...")
                                    continue
                    
                    # If we're out of retries, fail
                    if attempt >= max_retries:
                        logger.error(f"Authentication failed after {max_retries + 1} attempts")
                        return False
            
            return False
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Authentication failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response headers: {dict(e.response.headers)}")
                try:
                    logger.error(f"Response body: {e.response.text[:500]}")
                except:
                    pass
            return False
    
    def get_daily_readings(
        self,
        podmiot_id: str,
        punkt_sieci: str,
        date_from: datetime,
        date_to: datetime
    ) -> Optional[List[Dict]]:
        """
        Fetch daily water consumption readings.
        
        Args:
            podmiot_id: Entity ID (podmiot)
            punkt_sieci: Network point ID
            date_from: Start date
            date_to: End date
            
        Returns:
            List of daily readings or None if failed
        """
        url = f"{self.BASE_URL}/podmioty/{podmiot_id}/punkty-sieci/{punkt_sieci}/odczyty/dobowe"
        
        params = {
            'dataOd': date_from.strftime('%Y-%m-%dT%H:%M:%S'),
            'dataDo': date_to.strftime('%Y-%m-%dT%H:%M:%S')
        }
        
        try:
            logger.info(f"Fetching daily readings from {date_from} to {date_to}...")
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            readings = data.get('odczyty', [])
            logger.info(f"Retrieved {len(readings)} daily readings")
            return readings
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch daily readings: {e}")
            return None
    
    def get_hourly_readings(
        self,
        podmiot_id: str,
        punkt_sieci: str,
        date_from: datetime,
        date_to: datetime
    ) -> Optional[List[Dict]]:
        """
        Fetch hourly water consumption readings.
        
        Args:
            podmiot_id: Entity ID (podmiot)
            punkt_sieci: Network point ID
            date_from: Start date
            date_to: End date
            
        Returns:
            List of hourly readings or None if failed
        """
        url = f"{self.BASE_URL}/podmioty/{podmiot_id}/punkty-sieci/{punkt_sieci}/odczyty/godzinowe"
        
        params = {
            'dataOd': date_from.strftime('%Y-%m-%dT%H:%M:%S'),
            'dataDo': date_to.strftime('%Y-%m-%dT%H:%M:%S')
        }
        
        try:
            logger.info(f"Fetching hourly readings from {date_from} to {date_to}...")
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            readings = data.get('odczyty', [])
            logger.info(f"Retrieved {len(readings)} hourly readings")
            return readings
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch hourly readings: {e}")
            return None
    
    def get_punkty_sieci(
        self,
        podmiot_id: str,
        status: str = "AKTYWNE"
    ) -> Optional[List[Dict]]:
        """
        Fetch list of network points (meters) available for this account.
        
        Args:
            podmiot_id: Entity ID (podmiot)
            status: Filter by status (default: "AKTYWNE" for active meters)
            
        Returns:
            List of network points or None if failed
        """
        url = f"{self.BASE_URL}/podmioty/{podmiot_id}/punkty-sieci"
        
        params = {
            'status': status
        }
        
        try:
            logger.info(f"Fetching network points for podmiot {podmiot_id}...")
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            punkty = data.get('punkty', [])
            logger.info(f"Retrieved {len(punkty)} network points")
            return punkty
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch network points: {e}")
            return None
    
    def print_punkty_sieci(self, punkty: List[Dict]):
        """
        Print network points (meters) in a formatted way.
        
        Args:
            punkty: List of network point dictionaries
        """
        if not punkty:
            logger.warning("No network points to display")
            return
        
        print(f"\n{'='*100}")
        print(f"AVAILABLE NETWORK POINTS (METERS)")
        print(f"{'='*100}")
        print(f"{'ID':<12} {'Number':<15} {'Address':<40} {'Status':<10} {'Coordinates':<20}")
        print(f"{'-'*100}")
        
        for punkt in punkty:
            id_punktu = punkt.get('id_punktu', 'N/A')
            numer = punkt.get('numer', 'N/A')
            adres = punkt.get('adres', 'N/A')
            aktywny = "Active" if punkt.get('aktywny', False) else "Inactive"
            
            # Format coordinates
            wspolrzedne = punkt.get('wspolrzedne', {})
            if wspolrzedne:
                szerokosc = wspolrzedne.get('szerokosc', '')
                dlugosc = wspolrzedne.get('dlugosc', '')
                coords = f"{szerokosc:.6f}, {dlugosc:.6f}" if szerokosc and dlugosc else "N/A"
            else:
                coords = "N/A"
            
            # Truncate address if too long
            if len(adres) > 38:
                adres = adres[:35] + "..."
            
            print(f"{str(id_punktu):<12} {numer:<15} {adres:<40} {aktywny:<10} {coords:<20}")
        
        print(f"{'-'*100}")
        print(f"Total network points: {len(punkty)}")
        print(f"{'='*100}\n")
    
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
