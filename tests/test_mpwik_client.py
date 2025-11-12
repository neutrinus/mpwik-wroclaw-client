#!/usr/bin/env python3
"""
Comprehensive tests for MPWiKClient (API mode)
Tests all functionality of the API client with mocked HTTP requests
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timedelta
import json
import requests
from pathlib import Path
import tempfile
import os

from mpwik_direct import MPWiKClient


class TestMPWiKClientInitialization(unittest.TestCase):
    """Test client initialization and configuration."""
    
    def test_init_basic(self):
        """Test basic initialization with required parameters."""
        client = MPWiKClient(login="test_login", password="test_password")
        
        self.assertEqual(client.login, "test_login")
        self.assertEqual(client.password, "test_password")
        self.assertIsNone(client.recaptcha_api_key)
        self.assertIsNone(client.token)
        self.assertIsNone(client.csrf_token)
        self.assertFalse(client.debug)
    
    def test_init_with_recaptcha(self):
        """Test initialization with ReCAPTCHA configuration."""
        client = MPWiKClient(
            login="test_login",
            password="test_password",
            recaptcha_api_key="test_key",
            recaptcha_version=3
        )
        
        self.assertEqual(client.recaptcha_api_key, "test_key")
        self.assertEqual(client.recaptcha_version, 3)
    
    def test_init_with_debug(self):
        """Test initialization with debug mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = MPWiKClient(
                login="test_login",
                password="test_password",
                debug=True,
                log_dir=tmpdir
            )
            
            self.assertTrue(client.debug)
            self.assertEqual(client.log_dir, tmpdir)
    
    def test_session_headers_configured(self):
        """Test that session headers are properly configured."""
        client = MPWiKClient(login="test_login", password="test_password")
        
        self.assertIn('Content-Type', client.session.headers)
        self.assertIn('User-Agent', client.session.headers)
        self.assertIn('Origin', client.session.headers)
        self.assertIn('Referer', client.session.headers)
        self.assertEqual(client.session.headers['Content-Type'], 'application/json')
        self.assertEqual(client.session.headers['Origin'], MPWiKClient.SITE_URL)


class TestMPWiKClientAuthentication(unittest.TestCase):
    """Test authentication flow."""
    
    def setUp(self):
        """Set up test client."""
        self.client = MPWiKClient(login="test_login", password="test_password")
    
    @patch('mpwik_direct.requests.Session.get')
    @patch('mpwik_direct.requests.Session.post')
    def test_authenticate_success(self, mock_post, mock_get):
        """Test successful authentication without ReCAPTCHA."""
        # Mock the login page response
        mock_login_page = Mock()
        mock_login_page.status_code = 200
        mock_login_page.text = '<html><meta name="csrf" content="test_csrf_token"></html>'
        mock_login_page.raise_for_status = Mock()
        
        # Mock the session info response
        mock_session_info = Mock()
        mock_session_info.status_code = 200
        mock_session_info.json.return_value = {"csrfToken": "test_csrf_token"}
        mock_session_info.raise_for_status = Mock()
        
        # Mock the login response
        mock_login_response = Mock()
        mock_login_response.status_code = 200
        mock_login_response.json.return_value = {"token": "test_auth_token"}
        mock_login_response.headers = {}
        
        # Configure mocks
        mock_get.side_effect = [mock_login_page, mock_session_info]
        mock_post.return_value = mock_login_response
        
        # Test authentication
        result = self.client.authenticate()
        
        self.assertTrue(result)
        self.assertEqual(self.client.token, "test_auth_token")
        self.assertIn('Authorization', self.client.session.headers)
        self.assertEqual(self.client.session.headers['Authorization'], 'Bearer test_auth_token')
    
    @patch('mpwik_direct.requests.Session.get')
    @patch('mpwik_direct.requests.Session.post')
    def test_authenticate_failure(self, mock_post, mock_get):
        """Test authentication failure."""
        # Mock the login page response
        mock_login_page = Mock()
        mock_login_page.status_code = 200
        mock_login_page.text = '<html></html>'
        mock_login_page.raise_for_status = Mock()
        
        # Mock the session info response
        mock_session_info = Mock()
        mock_session_info.status_code = 200
        mock_session_info.json.return_value = {}
        
        # Mock the login failure response
        mock_login_response = Mock()
        mock_login_response.status_code = 401
        mock_login_response.json.return_value = {"error": "Invalid credentials"}
        mock_login_response.headers = {}
        
        mock_get.side_effect = [mock_login_page, mock_session_info]
        mock_post.return_value = mock_login_response
        
        # Test authentication failure
        result = self.client.authenticate()
        
        self.assertFalse(result)
        self.assertIsNone(self.client.token)
    
    @patch('mpwik_direct.requests.Session.get')
    @patch('mpwik_direct.requests.Session.post')
    def test_authenticate_with_csrf_token(self, mock_post, mock_get):
        """Test authentication with CSRF token extraction."""
        # Mock responses
        mock_login_page = Mock()
        mock_login_page.status_code = 200
        mock_login_page.text = '<html></html>'
        mock_login_page.raise_for_status = Mock()
        
        mock_session_info = Mock()
        mock_session_info.status_code = 200
        mock_session_info.json.return_value = {"csrfToken": "extracted_csrf_token"}
        
        mock_login_response = Mock()
        mock_login_response.status_code = 200
        mock_login_response.json.return_value = {"token": "test_auth_token"}
        mock_login_response.headers = {}
        
        mock_get.side_effect = [mock_login_page, mock_session_info]
        mock_post.return_value = mock_login_response
        
        result = self.client.authenticate()
        
        self.assertTrue(result)
        self.assertEqual(self.client.csrf_token, "extracted_csrf_token")
    
    @patch('mpwik_direct.requests.Session.get')
    @patch('mpwik_direct.requests.Session.post')
    def test_authenticate_retry_mechanism(self, mock_post, mock_get):
        """Test authentication retry on failure."""
        # Mock login page and session info
        mock_login_page = Mock()
        mock_login_page.status_code = 200
        mock_login_page.text = '<html></html>'
        mock_login_page.raise_for_status = Mock()
        
        mock_session_info = Mock()
        mock_session_info.status_code = 200
        mock_session_info.json.return_value = {}
        
        # First attempt fails, second succeeds
        mock_login_fail = Mock()
        mock_login_fail.status_code = 401
        mock_login_fail.json.return_value = {"error": "ReCAPTCHA required"}
        mock_login_fail.headers = {}
        
        mock_login_success = Mock()
        mock_login_success.status_code = 200
        mock_login_success.json.return_value = {"token": "test_auth_token"}
        mock_login_success.headers = {}
        
        mock_get.side_effect = [mock_login_page, mock_session_info]
        mock_post.side_effect = [mock_login_fail, mock_login_success]
        
        result = self.client.authenticate(max_retries=2)
        
        self.assertTrue(result)
        self.assertEqual(mock_post.call_count, 2)


class TestMPWiKClientReCAPTCHA(unittest.TestCase):
    """Test ReCAPTCHA solving functionality."""
    
    def setUp(self):
        """Set up test client with ReCAPTCHA API key."""
        self.client = MPWiKClient(
            login="test_login",
            password="test_password",
            recaptcha_api_key="test_capmonster_key",
            recaptcha_version=3
        )
    
    @patch('mpwik_direct.requests.post')
    @patch('mpwik_direct.time.sleep')
    def test_solve_recaptcha_v3_success(self, mock_sleep, mock_post):
        """Test successful ReCAPTCHA v3 solving."""
        # Mock create task response
        mock_create_response = Mock()
        mock_create_response.status_code = 200
        mock_create_response.json.return_value = {
            "errorId": 0,
            "taskId": "test_task_id_123"
        }
        mock_create_response.raise_for_status = Mock()
        
        # Mock result response (ready)
        mock_result_response = Mock()
        mock_result_response.status_code = 200
        mock_result_response.json.return_value = {
            "status": "ready",
            "solution": {"gRecaptchaResponse": "test_recaptcha_token"}
        }
        mock_result_response.raise_for_status = Mock()
        
        mock_post.side_effect = [mock_create_response, mock_result_response]
        
        token = self.client.solve_recaptcha("test_site_key", recaptcha_version=3)
        
        self.assertEqual(token, "test_recaptcha_token")
        self.assertEqual(mock_post.call_count, 2)
    
    @patch('mpwik_direct.requests.post')
    @patch('mpwik_direct.time.sleep')
    def test_solve_recaptcha_v2_success(self, mock_sleep, mock_post):
        """Test successful ReCAPTCHA v2 solving."""
        mock_create_response = Mock()
        mock_create_response.status_code = 200
        mock_create_response.json.return_value = {
            "errorId": 0,
            "taskId": "test_task_id_456"
        }
        mock_create_response.raise_for_status = Mock()
        
        mock_result_response = Mock()
        mock_result_response.status_code = 200
        mock_result_response.json.return_value = {
            "status": "ready",
            "solution": {"gRecaptchaResponse": "test_recaptcha_token_v2"}
        }
        mock_result_response.raise_for_status = Mock()
        
        mock_post.side_effect = [mock_create_response, mock_result_response]
        
        token = self.client.solve_recaptcha("test_site_key", recaptcha_version=2)
        
        self.assertEqual(token, "test_recaptcha_token_v2")
    
    @patch('mpwik_direct.requests.post')
    def test_solve_recaptcha_capmonster_error(self, mock_post):
        """Test ReCAPTCHA solving with CapMonster error."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "errorId": 1,
            "errorDescription": "Invalid API key"
        }
        mock_response.raise_for_status = Mock()
        
        mock_post.return_value = mock_response
        
        token = self.client.solve_recaptcha("test_site_key")
        
        self.assertIsNone(token)
    
    def test_solve_recaptcha_no_api_key(self):
        """Test ReCAPTCHA solving without API key."""
        client = MPWiKClient(login="test", password="test")
        token = client.solve_recaptcha("test_site_key")
        
        self.assertIsNone(token)


class TestMPWiKClientDataFetching(unittest.TestCase):
    """Test data fetching methods."""
    
    def setUp(self):
        """Set up authenticated test client."""
        self.client = MPWiKClient(login="test_login", password="test_password")
        self.client.token = "test_auth_token"
        self.client.session.headers['Authorization'] = f'Bearer {self.client.token}'
    
    @patch('mpwik_direct.requests.Session.get')
    def test_get_daily_readings_success(self, mock_get):
        """Test successful daily readings fetch."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "odczyty": [
                {"data": "2024-01-01", "wskazanie": 100.5, "zuzycie": 2.3},
                {"data": "2024-01-02", "wskazanie": 102.8, "zuzycie": 2.3}
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 1, 2)
        
        readings = self.client.get_daily_readings("123", "0123-2021", date_from, date_to)
        
        self.assertIsNotNone(readings)
        self.assertEqual(len(readings), 2)
        self.assertEqual(readings[0]['data'], "2024-01-01")
        self.assertEqual(readings[1]['zuzycie'], 2.3)
    
    @patch('mpwik_direct.requests.Session.get')
    def test_get_daily_readings_failure(self, mock_get):
        """Test daily readings fetch failure."""
        mock_get.side_effect = requests.exceptions.RequestException("Network error")
        
        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 1, 2)
        
        readings = self.client.get_daily_readings("123", "0123-2021", date_from, date_to)
        
        self.assertIsNone(readings)
    
    @patch('mpwik_direct.requests.Session.get')
    def test_get_hourly_readings_success(self, mock_get):
        """Test successful hourly readings fetch."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "odczyty": [
                {"data": "2024-01-01T00:00:00", "wskazanie": 100.0, "zuzycie": 0.1},
                {"data": "2024-01-01T01:00:00", "wskazanie": 100.1, "zuzycie": 0.1}
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        date_from = datetime(2024, 1, 1, 0, 0, 0)
        date_to = datetime(2024, 1, 1, 23, 59, 59)
        
        readings = self.client.get_hourly_readings("123", "0123-2021", date_from, date_to)
        
        self.assertIsNotNone(readings)
        self.assertEqual(len(readings), 2)
    
    @patch('mpwik_direct.requests.Session.get')
    def test_get_punkty_sieci_success(self, mock_get):
        """Test successful network points fetch."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "punkty": [
                {
                    "id_punktu": "123",
                    "numer": "0123/2021",
                    "adres": "Test Street 1",
                    "aktywny": True
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        punkty = self.client.get_punkty_sieci("123")
        
        self.assertIsNotNone(punkty)
        self.assertEqual(len(punkty), 1)
        self.assertEqual(punkty[0]['numer'], "0123/2021")
        self.assertTrue(punkty[0]['aktywny'])
    
    @patch('mpwik_direct.requests.Session.get')
    def test_get_punkty_sieci_with_status_filter(self, mock_get):
        """Test network points fetch with status filter."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"punkty": []}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        self.client.get_punkty_sieci("123", status="NIEAKTYWNE")
        
        # Verify the status parameter was passed
        call_args = mock_get.call_args
        self.assertIn('params', call_args[1])
        self.assertEqual(call_args[1]['params']['status'], "NIEAKTYWNE")


class TestMPWiKClientLogging(unittest.TestCase):
    """Test logging functionality."""
    
    def test_save_request_log_when_debug_disabled(self):
        """Test that logs are not saved when debug is disabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = MPWiKClient(
                login="test",
                password="test",
                debug=False,
                log_dir=tmpdir
            )
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {}
            mock_response.headers = {}
            mock_response.elapsed.total_seconds.return_value = 0.5
            
            client._save_request_log(
                "test_request",
                "https://test.com",
                "GET",
                {},
                None,
                mock_response
            )
            
            # Check that no log files were created
            log_dir = Path(tmpdir) / "requests"
            if log_dir.exists():
                self.assertEqual(len(list(log_dir.glob("*.json"))), 0)
    
    def test_save_request_log_when_debug_enabled(self):
        """Test that logs are saved when debug is enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = MPWiKClient(
                login="test",
                password="test",
                debug=True,
                log_dir=tmpdir
            )
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": "success"}
            mock_response.headers = {"Content-Type": "application/json"}
            mock_response.elapsed.total_seconds.return_value = 0.5
            mock_response.reason = "OK"
            
            client._save_request_log(
                "test_request",
                "https://test.com/api",
                "GET",
                {"Authorization": "Bearer token"},
                None,
                mock_response
            )
            
            # Check that log file was created
            log_dir = Path(tmpdir) / "requests"
            self.assertTrue(log_dir.exists())
            log_files = list(log_dir.glob("*.json"))
            self.assertGreater(len(log_files), 0)
            
            # Verify log content
            with open(log_files[0], 'r') as f:
                log_data = json.load(f)
                self.assertEqual(log_data['request_type'], "test_request")
                self.assertEqual(log_data['method'], "GET")
                self.assertEqual(log_data['response']['status_code'], 200)
    
    def test_save_request_log_sanitizes_password(self):
        """Test that passwords are sanitized in logs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = MPWiKClient(
                login="test",
                password="secret_password",
                debug=True,
                log_dir=tmpdir
            )
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {}
            mock_response.headers = {}
            mock_response.elapsed.total_seconds.return_value = 0.5
            mock_response.reason = "OK"
            
            payload = {
                "login": "test",
                "password": "secret_password"
            }
            
            client._save_request_log(
                "login",
                "https://test.com/login",
                "POST",
                {},
                payload,
                mock_response
            )
            
            # Check that password was sanitized
            log_dir = Path(tmpdir) / "requests"
            log_files = list(log_dir.glob("*.json"))
            
            with open(log_files[0], 'r') as f:
                log_data = json.load(f)
                self.assertEqual(log_data['payload']['password'], '***')
                self.assertNotEqual(log_data['payload']['password'], 'secret_password')


class TestMPWiKClientPrintMethods(unittest.TestCase):
    """Test print/display methods."""
    
    def setUp(self):
        """Set up test client."""
        self.client = MPWiKClient(login="test", password="test")
    
    @patch('builtins.print')
    def test_print_punkty_sieci(self, mock_print):
        """Test printing network points."""
        punkty = [
            {
                "id_punktu": "123",
                "numer": "0123/2021",
                "adres": "Test Street 1, Wrocław",
                "aktywny": True,
                "wspolrzedne": {"szerokosc": 51.1128, "dlugosc": 17.0262}
            }
        ]
        
        self.client.print_punkty_sieci(punkty)
        
        # Verify print was called
        self.assertGreater(mock_print.call_count, 0)
    
    def test_print_punkty_sieci_empty(self):
        """Test printing empty network points list."""
        # Should log warning but not crash
        # The function returns early without printing when empty
        self.client.print_punkty_sieci([])
        # No assertion needed - just verify it doesn't crash
    
    @patch('builtins.print')
    def test_print_readings(self, mock_print):
        """Test printing readings."""
        readings = [
            {
                "data": "2024-01-01",
                "licznik": "0123/2021",
                "wskazanie": 100.5,
                "zuzycie": 2.3,
                "typ": "DAILY"
            },
            {
                "data": "2024-01-02",
                "licznik": "0123/2021",
                "wskazanie": 102.8,
                "zuzycie": 2.3,
                "typ": "DAILY"
            }
        ]
        
        self.client.print_readings(readings, "daily")
        
        # Verify print was called multiple times
        self.assertGreater(mock_print.call_count, 5)


class TestMPWiKClientAttemptLogin(unittest.TestCase):
    """Test the _attempt_login internal method."""
    
    def setUp(self):
        """Set up test client."""
        self.client = MPWiKClient(login="test_login", password="test_password")
    
    @patch('mpwik_direct.requests.Session.post')
    def test_attempt_login_with_recaptcha_token(self, mock_post):
        """Test login attempt with ReCAPTCHA token in header."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token": "auth_token"}
        mock_response.headers = {}
        mock_post.return_value = mock_response
        
        success, data, response = self.client._attempt_login(
            recaptcha_token="test_recaptcha_token",
            csrf_token="test_csrf_token"
        )
        
        self.assertTrue(success)
        self.assertIsNotNone(data)
        self.assertEqual(data['token'], "auth_token")
        
        # Verify headers were set correctly
        call_args = mock_post.call_args
        headers = call_args[1]['headers']
        self.assertIn('X-RECAPTCHA-TOKEN', headers)
        self.assertEqual(headers['X-RECAPTCHA-TOKEN'], "test_recaptcha_token")
        self.assertIn('X-CSRF-TOKEN', headers)
    
    @patch('mpwik_direct.requests.Session.post')
    def test_attempt_login_without_tokens(self, mock_post):
        """Test login attempt without ReCAPTCHA or CSRF tokens."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token": "auth_token"}
        mock_response.headers = {}
        mock_post.return_value = mock_response
        
        success, data, response = self.client._attempt_login()
        
        self.assertTrue(success)
        
        # Verify no special tokens in headers
        call_args = mock_post.call_args
        headers = call_args[1]['headers']
        self.assertNotIn('X-RECAPTCHA-TOKEN', headers)
        self.assertNotIn('X-CSRF-TOKEN', headers)


def main():
    """Run all tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestMPWiKClientInitialization))
    suite.addTests(loader.loadTestsFromTestCase(TestMPWiKClientAuthentication))
    suite.addTests(loader.loadTestsFromTestCase(TestMPWiKClientReCAPTCHA))
    suite.addTests(loader.loadTestsFromTestCase(TestMPWiKClientDataFetching))
    suite.addTests(loader.loadTestsFromTestCase(TestMPWiKClientLogging))
    suite.addTests(loader.loadTestsFromTestCase(TestMPWiKClientPrintMethods))
    suite.addTests(loader.loadTestsFromTestCase(TestMPWiKClientAttemptLogin))
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
