#!/usr/bin/env python3
"""
Comprehensive tests for MPWiKBrowserClient (browser automation mode)
Tests all functionality of the browser client with mocked Selenium WebDriver
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, call, PropertyMock
from datetime import datetime, timedelta
import json
import tempfile
from pathlib import Path

from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

from mpwik_selenium import MPWiKBrowserClient


class TestMPWiKBrowserClientInitialization(unittest.TestCase):
    """Test browser client initialization."""
    
    @patch('mpwik_browser_client.ChromeDriverManager')
    def test_init_basic(self, mock_manager):
        """Test basic initialization."""
        client = MPWiKBrowserClient(
            login="test_login",
            password="test_password",
            headless=True
        )
        
        self.assertEqual(client.login, "test_login")
        self.assertEqual(client.password, "test_password")
        self.assertTrue(client.headless)
        self.assertIsNone(client.driver)
        self.assertFalse(client.authenticated)
    
    @patch('mpwik_browser_client.ChromeDriverManager')
    def test_init_with_debug(self, mock_manager):
        """Test initialization with debug mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = MPWiKBrowserClient(
                login="test_login",
                password="test_password",
                debug=True,
                log_dir=tmpdir
            )
            
            self.assertTrue(client.debug)
            self.assertEqual(str(client.log_dir), tmpdir)
            self.assertIsNotNone(client.requests_log_dir)
    
    @patch('mpwik_browser_client.ChromeDriverManager')
    def test_init_without_debug(self, mock_manager):
        """Test initialization without debug mode."""
        client = MPWiKBrowserClient(
            login="test_login",
            password="test_password",
            debug=False
        )
        
        self.assertFalse(client.debug)
        self.assertIsNone(client.requests_log_dir)


class TestMPWiKBrowserClientDriverSetup(unittest.TestCase):
    """Test driver setup and configuration."""
    
    @patch('mpwik_browser_client.webdriver.Chrome')
    @patch('mpwik_browser_client.ChromeDriverManager')
    @patch('mpwik_browser_client.Service')
    def test_setup_driver_chrome(self, mock_service, mock_manager, mock_chrome):
        """Test Chrome driver setup."""
        mock_driver_instance = Mock()
        mock_chrome.return_value = mock_driver_instance
        mock_manager_instance = Mock()
        mock_manager.return_value = mock_manager_instance
        mock_manager_instance.install.return_value = "/path/to/chromedriver"
        
        client = MPWiKBrowserClient(
            login="test",
            password="test",
            headless=True
        )
        client._setup_driver()
        
        self.assertIsNotNone(client.driver)
        mock_chrome.assert_called_once()
    
    @patch('mpwik_browser_client.webdriver.Chrome')
    @patch('mpwik_browser_client.ChromeDriverManager')
    @patch('mpwik_browser_client.Service')
    def test_setup_driver_headless_option(self, mock_service, mock_manager, mock_chrome):
        """Test that headless option is properly configured."""
        mock_driver_instance = Mock()
        mock_chrome.return_value = mock_driver_instance
        mock_manager_instance = Mock()
        mock_manager.return_value = mock_manager_instance
        mock_manager_instance.install.return_value = "/path/to/chromedriver"
        
        client = MPWiKBrowserClient(
            login="test",
            password="test",
            headless=True
        )
        client._setup_driver()
        
        # Check that Chrome was called with options
        call_kwargs = mock_chrome.call_args[1]
        self.assertIn('options', call_kwargs)
    
    @patch('mpwik_browser_client.ChromeDriverManager')
    def test_setup_driver_already_initialized(self, mock_manager):
        """Test that setup_driver doesn't reinitialize if driver exists."""
        client = MPWiKBrowserClient(login="test", password="test")
        mock_driver = Mock()
        client.driver = mock_driver
        
        client._setup_driver()
        
        # Driver should remain the same
        self.assertEqual(client.driver, mock_driver)


class TestMPWiKBrowserClientLogging(unittest.TestCase):
    """Test logging and debugging functionality."""
    
    @patch('mpwik_browser_client.ChromeDriverManager')
    def test_save_page_source_when_debug_disabled(self, mock_manager):
        """Test that page source is not saved when debug is disabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = MPWiKBrowserClient(
                login="test",
                password="test",
                debug=False,
                log_dir=tmpdir
            )
            client.driver = Mock()
            client.driver.page_source = "<html>test</html>"
            
            result = client._save_page_source("test")
            
            self.assertIsNone(result)
    
    @patch('mpwik_browser_client.ChromeDriverManager')
    def test_save_page_source_when_debug_enabled(self, mock_manager):
        """Test that page source is saved when debug is enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = MPWiKBrowserClient(
                login="test",
                password="test",
                debug=True,
                log_dir=tmpdir
            )
            client.driver = Mock()
            client.driver.page_source = "<html>test</html>"
            
            result = client._save_page_source("test")
            
            self.assertIsNotNone(result)
            self.assertTrue(result.exists())
            
            # Verify content
            with open(result, 'r') as f:
                content = f.read()
                self.assertIn("test", content)
    
    @patch('mpwik_browser_client.ChromeDriverManager')
    def test_save_screenshot_when_debug_disabled(self, mock_manager):
        """Test that screenshot is not saved when debug is disabled."""
        client = MPWiKBrowserClient(
            login="test",
            password="test",
            debug=False
        )
        client.driver = Mock()
        
        result = client._save_screenshot("test")
        
        self.assertIsNone(result)
        client.driver.save_screenshot.assert_not_called()
    
    @patch('mpwik_browser_client.ChromeDriverManager')
    def test_save_screenshot_when_debug_enabled(self, mock_manager):
        """Test that screenshot is saved when debug is enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = MPWiKBrowserClient(
                login="test",
                password="test",
                debug=True,
                log_dir=tmpdir
            )
            client.driver = Mock()
            
            result = client._save_screenshot("test")
            
            self.assertIsNotNone(result)
            client.driver.save_screenshot.assert_called_once()


class TestMPWiKBrowserClientAuthentication(unittest.TestCase):
    """Test authentication flow."""
    
    @patch('mpwik_browser_client.ChromeDriverManager')
    def test_fill_login_field_success(self, mock_manager):
        """Test successful login field filling."""
        client = MPWiKBrowserClient(login="test_login", password="test_password")
        
        # Mock driver that returns success
        mock_driver = Mock()
        mock_driver.execute_script.return_value = 'success'
        
        client.driver = mock_driver
        
        result = client._fill_login_field("test_login")
        
        self.assertTrue(result)
        mock_driver.execute_script.assert_called_once()
    
    @patch('mpwik_browser_client.ChromeDriverManager')
    def test_fill_login_field_timeout(self, mock_manager):
        """Test login field filling with error."""
        client = MPWiKBrowserClient(login="test", password="test")
        
        mock_driver = Mock()
        mock_driver.execute_script.return_value = 'login_field_not_found'
        
        client.driver = mock_driver
        
        result = client._fill_login_field("test")
        
        self.assertFalse(result)
    
    @patch('mpwik_browser_client.ChromeDriverManager')
    def test_fill_password_field_success(self, mock_manager):
        """Test successful password field filling."""
        client = MPWiKBrowserClient(login="test", password="test_password")
        
        mock_driver = Mock()
        mock_driver.execute_script.return_value = 'success'
        
        client.driver = mock_driver
        
        result = client._fill_password_field("test_password")
        
        self.assertTrue(result)
        mock_driver.execute_script.assert_called_once()
    
    @patch('mpwik_browser_client.ChromeDriverManager')
    def test_click_login_button_success(self, mock_manager):
        """Test successful login button click."""
        client = MPWiKBrowserClient(login="test", password="test")
        
        mock_driver = Mock()
        mock_driver.execute_script.return_value = 'success'
        
        client.driver = mock_driver
        
        result = client._click_login_button()
        
        self.assertTrue(result)
        mock_driver.execute_script.assert_called_once()


class TestMPWiKBrowserClientDataFetching(unittest.TestCase):
    """Test data fetching functionality."""
    
    @patch('mpwik_browser_client.ChromeDriverManager')
    def test_get_readings_from_api_success(self, mock_manager):
        """Test successful API data extraction from network logs."""
        client = MPWiKBrowserClient(login="test", password="test")
        client.authenticated = True  # Mark as authenticated
        
        # Mock driver
        mock_driver = Mock()
        mock_driver.current_url = "https://ebok.mpwik.wroc.pl/trust/zuzycie-wody?p=123"
        
        # Mock execute_async_script for fetch - must return dict with success and data
        mock_driver.execute_async_script.return_value = {
            "success": True,
            "data": {
                "odczyty": [
                    {"data": "2024-01-01", "wskazanie": 100.5, "zuzycie": 2.3}
                ]
            }
        }
        mock_driver.get_log.return_value = []  # Empty browser logs
        
        client.driver = mock_driver
        
        readings = client.get_readings_from_api(
            "123", "0123-2021", datetime(2024, 1, 1), datetime(2024, 1, 2), "daily"
        )
        
        self.assertIsNotNone(readings)
        self.assertEqual(len(readings), 1)
        self.assertEqual(readings[0]['zuzycie'], 2.3)
    
    @patch('mpwik_browser_client.ChromeDriverManager')
    def test_get_readings_from_api_not_found(self, mock_manager):
        """Test API data extraction when fetch fails."""
        client = MPWiKBrowserClient(login="test", password="test")
        client.authenticated = True  # Mark as authenticated
        
        mock_driver = Mock()
        mock_driver.current_url = "https://ebok.mpwik.wroc.pl/trust/zuzycie-wody?p=123"
        # Return failure to simulate failed fetch
        mock_driver.execute_async_script.return_value = {
            "success": False,
            "error": "API error"
        }
        mock_driver.get_log.return_value = []
        
        client.driver = mock_driver
        
        readings = client.get_readings_from_api(
            "123", "0123-2021", datetime(2024, 1, 1), datetime(2024, 1, 2), "daily"
        )
        
        self.assertIsNone(readings)
    
    @patch('mpwik_browser_client.ChromeDriverManager')
    def test_get_punkty_sieci_success(self, mock_manager):
        """Test successful network points extraction."""
        client = MPWiKBrowserClient(login="test", password="test")
        client.authenticated = True  # Mark as authenticated
        
        # Mock driver
        mock_driver = Mock()
        mock_driver.current_url = "https://ebok.mpwik.wroc.pl/trust/zuzycie-wody?p=123"
        
        # Mock execute_async_script for fetch
        mock_driver.execute_async_script.return_value = {
            "success": True,
            "data": {
                "punkty": [
                    {"id_punktu": "123", "numer": "0123/2021", "aktywny": True}
                ]
            }
        }
        mock_driver.get_log.return_value = []
        
        client.driver = mock_driver
        
        punkty = client.get_punkty_sieci("123")
        
        self.assertIsNotNone(punkty)
        self.assertEqual(len(punkty), 1)
        self.assertTrue(punkty[0]['aktywny'])


class TestMPWiKBrowserClientConvenienceMethods(unittest.TestCase):
    """Test convenience wrapper methods."""
    
    @patch('mpwik_browser_client.ChromeDriverManager')
    def test_get_daily_readings_calls_get_readings_from_api(self, mock_manager):
        """Test that get_daily_readings properly delegates to get_readings_from_api."""
        client = MPWiKBrowserClient(login="test", password="test")
        
        # Mock get_readings_from_api
        with patch.object(client, 'get_readings_from_api') as mock_get:
            mock_get.return_value = [{"data": "2024-01-01"}]
            
            result = client.get_daily_readings(
                "123", "0123-2021",
                datetime(2024, 1, 1), datetime(2024, 1, 2)
            )
            
            mock_get.assert_called_once()
            # Verify correct reading type was passed - implementation uses "daily"
            call_args = mock_get.call_args[0]
            self.assertEqual(call_args[4], "daily")  # 5th arg should be "daily"
    
    @patch('mpwik_browser_client.ChromeDriverManager')
    def test_get_hourly_readings_calls_get_readings_from_api(self, mock_manager):
        """Test that get_hourly_readings properly delegates to get_readings_from_api."""
        client = MPWiKBrowserClient(login="test", password="test")
        
        with patch.object(client, 'get_readings_from_api') as mock_get:
            mock_get.return_value = [{"data": "2024-01-01T00:00:00"}]
            
            result = client.get_hourly_readings(
                "123", "0123-2021",
                datetime(2024, 1, 1), datetime(2024, 1, 1)
            )
            
            mock_get.assert_called_once()
            # Verify correct reading type was passed - implementation uses "hourly"
            call_args = mock_get.call_args[0]
            self.assertEqual(call_args[4], "hourly")  # 5th arg should be "hourly"


class TestMPWiKBrowserClientContextManager(unittest.TestCase):
    """Test context manager behavior."""
    
    @patch('mpwik_browser_client.webdriver.Chrome')
    @patch('mpwik_browser_client.ChromeDriverManager')
    @patch('mpwik_browser_client.Service')
    def test_context_manager_enter(self, mock_service, mock_manager, mock_chrome):
        """Test context manager __enter__ method."""
        mock_driver_instance = Mock()
        mock_chrome.return_value = mock_driver_instance
        mock_manager_instance = Mock()
        mock_manager.return_value = mock_manager_instance
        mock_manager_instance.install.return_value = "/path/to/chromedriver"
        
        client = MPWiKBrowserClient(login="test", password="test")
        # Context manager __enter__ doesn't setup driver automatically
        # It just returns self
        entered_client = client.__enter__()
        
        self.assertEqual(entered_client, client)
        # Driver is None until _setup_driver is called
        self.assertIsNone(client.driver)
    
    @patch('mpwik_browser_client.webdriver.Chrome')
    @patch('mpwik_browser_client.ChromeDriverManager')
    @patch('mpwik_browser_client.Service')
    def test_context_manager_exit_closes_driver(self, mock_service, mock_manager, mock_chrome):
        """Test context manager __exit__ method closes driver."""
        mock_driver_instance = Mock()
        mock_chrome.return_value = mock_driver_instance
        mock_manager_instance = Mock()
        mock_manager.return_value = mock_manager_instance
        mock_manager_instance.install.return_value = "/path/to/chromedriver"
        
        client = MPWiKBrowserClient(login="test", password="test")
        client._setup_driver()
        
        # Manually call __exit__ to test
        client.__exit__(None, None, None)
        
        # Driver should be quit
        mock_driver_instance.quit.assert_called_once()
    
    @patch('mpwik_browser_client.ChromeDriverManager')
    def test_close_method(self, mock_manager):
        """Test close method."""
        client = MPWiKBrowserClient(login="test", password="test")
        mock_driver = Mock()
        client.driver = mock_driver
        
        client.close()
        
        mock_driver.quit.assert_called_once()
        self.assertIsNone(client.driver)
    
    @patch('mpwik_browser_client.ChromeDriverManager')
    def test_close_method_no_driver(self, mock_manager):
        """Test close method when driver is None."""
        client = MPWiKBrowserClient(login="test", password="test")
        client.driver = None
        
        # Should not raise exception
        client.close()
        
        self.assertIsNone(client.driver)


class TestMPWiKBrowserClientNetworkLogs(unittest.TestCase):
    """Test network logging functionality."""
    
    @patch('mpwik_browser_client.ChromeDriverManager')
    def test_save_network_logs_when_debug_disabled(self, mock_manager):
        """Test that network logs are not saved when debug is disabled."""
        client = MPWiKBrowserClient(
            login="test",
            password="test",
            debug=False
        )
        mock_driver = Mock()
        mock_driver.get_log.return_value = []
        client.driver = mock_driver
        
        result = client._save_network_logs("test")
        
        self.assertIsNone(result)
    
    @patch('mpwik_browser_client.ChromeDriverManager')
    def test_save_network_logs_when_debug_enabled(self, mock_manager):
        """Test that network logs are saved when debug is enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = MPWiKBrowserClient(
                login="test",
                password="test",
                debug=True,
                log_dir=tmpdir
            )
            mock_driver = Mock()
            # Network logs are filtered by method starting with "Network."
            mock_driver.get_log.return_value = [
                {
                    "timestamp": 1234567890,
                    "level": "INFO",
                    "message": json.dumps({
                        "message": {
                            "method": "Network.requestWillBeSent",
                            "params": {"requestId": "123", "request": {"url": "https://test.com"}}
                        }
                    })
                }
            ]
            client.driver = mock_driver
            
            result = client._save_network_logs("test")
            
            self.assertIsNotNone(result)
            self.assertTrue(result.exists())
            
            # Verify content - should have network events
            with open(result, 'r') as f:
                content = json.load(f)
                self.assertEqual(len(content), 1)
                self.assertEqual(content[0]['method'], "Network.requestWillBeSent")


class TestMPWiKBrowserClientErrorHandling(unittest.TestCase):
    """Test error handling in browser client."""
    
    @patch('mpwik_browser_client.ChromeDriverManager')
    def test_webdriver_exception_handling_in_save_detailed_logs(self, mock_manager):
        """Test that WebDriverException is handled gracefully in detailed logs."""
        client = MPWiKBrowserClient(
            login="test",
            password="test",
            debug=True
        )
        
        mock_driver = Mock()
        mock_driver.get_log.return_value = []
        mock_driver.execute_cdp_cmd.side_effect = WebDriverException(
            "No resource with given identifier found"
        )
        
        client.driver = mock_driver
        
        # Should not raise exception
        try:
            client._save_detailed_network_logs("test")
        except WebDriverException:
            self.fail("WebDriverException should have been handled")
    
    @patch('mpwik_browser_client.ChromeDriverManager')
    def test_timeout_exception_in_fill_login_field(self, mock_manager):
        """Test exception handling in login field filling."""
        client = MPWiKBrowserClient(login="test", password="test")
        
        mock_driver = Mock()
        mock_driver.execute_script.side_effect = Exception("JavaScript error")
        
        client.driver = mock_driver
        
        result = client._fill_login_field("test")
        
        self.assertFalse(result)
    
    @patch('mpwik_browser_client.ChromeDriverManager')
    def test_nosuchelement_exception_in_click_login_button(self, mock_manager):
        """Test error handling in login button click."""
        client = MPWiKBrowserClient(login="test", password="test")
        
        mock_driver = Mock()
        mock_driver.execute_script.return_value = 'button_not_found'
        
        client.driver = mock_driver
        
        result = client._click_login_button()
        
        self.assertFalse(result)


class TestMPWiKBrowserClientPrintMethods(unittest.TestCase):
    """Test print/display methods."""
    
    @patch('mpwik_browser_client.ChromeDriverManager')
    @patch('builtins.print')
    def test_print_readings(self, mock_print, mock_manager):
        """Test printing readings."""
        client = MPWiKBrowserClient(login="test", password="test")
        
        readings = [
            {
                "data": "2024-01-01",
                "licznik": "0123/2021",
                "wskazanie": 100.5,
                "zuzycie": 2.3,
                "typ": "DAILY"
            }
        ]
        
        client.print_readings(readings, "daily")
        
        # Verify print was called
        self.assertGreater(mock_print.call_count, 0)


def main():
    """Run all tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestMPWiKBrowserClientInitialization))
    suite.addTests(loader.loadTestsFromTestCase(TestMPWiKBrowserClientDriverSetup))
    suite.addTests(loader.loadTestsFromTestCase(TestMPWiKBrowserClientLogging))
    suite.addTests(loader.loadTestsFromTestCase(TestMPWiKBrowserClientAuthentication))
    suite.addTests(loader.loadTestsFromTestCase(TestMPWiKBrowserClientDataFetching))
    suite.addTests(loader.loadTestsFromTestCase(TestMPWiKBrowserClientConvenienceMethods))
    suite.addTests(loader.loadTestsFromTestCase(TestMPWiKBrowserClientContextManager))
    suite.addTests(loader.loadTestsFromTestCase(TestMPWiKBrowserClientNetworkLogs))
    suite.addTests(loader.loadTestsFromTestCase(TestMPWiKBrowserClientErrorHandling))
    suite.addTests(loader.loadTestsFromTestCase(TestMPWiKBrowserClientPrintMethods))
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
