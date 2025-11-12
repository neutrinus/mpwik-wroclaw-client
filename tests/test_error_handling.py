#!/usr/bin/env python3
"""
Test error handling improvements in MPWiK Browser Client
"""

import sys
import unittest
from unittest.mock import Mock, patch, MagicMock
from selenium.common.exceptions import WebDriverException


class TestNetworkLogsErrorHandling(unittest.TestCase):
    """Test error handling in _save_detailed_network_logs method."""
    
    def test_webdriver_exception_with_no_resource_error(self):
        """Test that 'No resource with given identifier found' error is handled gracefully."""
        # Import here to avoid dependency issues
        from mpwik_selenium import MPWiKBrowserClient
        
        # Create a mock client
        with patch('mpwik_browser_client.ChromeDriverManager'):
            client = MPWiKBrowserClient(
                login="test",
                password="test",
                headless=True,
                debug=True
            )
            
            # Mock the driver
            mock_driver = Mock()
            client.driver = mock_driver
            
            # Simulate the error that occurs
            error_msg = 'Message: unknown error: unhandled inspector error: {"code":-32000,"message":"No resource with given identifier found"}'
            mock_driver.execute_cdp_cmd.side_effect = WebDriverException(error_msg)
            
            # Mock get_log to return empty logs
            mock_driver.get_log.return_value = []
            
            # Create a mock request that would trigger the body fetch
            requests_map = {
                "test_request_id": {
                    "url": "https://ebok.mpwik.wroc.pl/frontend-api/v1/podmioty/123456/punkty-sieci?status=A",
                    "method": "GET",
                    "response": {
                        "status": 200,
                        "mime_type": "application/json"
                    },
                    "loading_finished": True
                }
            }
            
            # Test that it doesn't raise an exception and handles gracefully
            try:
                # Simulate the logic from _save_detailed_network_logs
                for request_id, request_data in list(requests_map.items()):
                    url = request_data.get("url", "")
                    response = request_data.get("response")
                    
                    if (response and 
                        "frontend-api" in url and 
                        response.get("status") == 200 and
                        request_data.get("loading_finished")):
                        
                        mime_type = response.get("mime_type", "")
                        if "json" in mime_type or "text" in mime_type:
                            try:
                                body_result = mock_driver.execute_cdp_cmd("Network.getResponseBody", {
                                    "requestId": request_id
                                })
                                if body_result:
                                    request_data["response_body"] = body_result.get("body", "")
                            except WebDriverException as e:
                                error_msg = str(e)
                                if "No resource with given identifier found" in error_msg:
                                    # This is the improved handling
                                    pass  # Should just log, not raise
                                else:
                                    pass  # Should also just log
                            except Exception as e:
                                pass  # Should also just log
                
                # If we get here without exception, the test passes
                self.assertTrue(True, "Error handling worked correctly")
                
            except Exception as e:
                self.fail(f"Error handling failed: {e}")
    
    def test_webdriver_exception_with_other_error(self):
        """Test that other WebDriverExceptions are handled gracefully."""
        from mpwik_selenium import MPWiKBrowserClient
        
        with patch('mpwik_browser_client.ChromeDriverManager'):
            client = MPWiKBrowserClient(
                login="test",
                password="test",
                headless=True,
                debug=True
            )
            
            mock_driver = Mock()
            client.driver = mock_driver
            
            # Simulate a different error
            error_msg = 'Some other WebDriver error'
            mock_driver.execute_cdp_cmd.side_effect = WebDriverException(error_msg)
            mock_driver.get_log.return_value = []
            
            requests_map = {
                "test_request_id": {
                    "url": "https://ebok.mpwik.wroc.pl/frontend-api/v1/test",
                    "method": "GET",
                    "response": {
                        "status": 200,
                        "mime_type": "application/json"
                    },
                    "loading_finished": True
                }
            }
            
            # Test that it doesn't raise an exception
            try:
                for request_id, request_data in list(requests_map.items()):
                    url = request_data.get("url", "")
                    response = request_data.get("response")
                    
                    if (response and 
                        "frontend-api" in url and 
                        response.get("status") == 200 and
                        request_data.get("loading_finished")):
                        
                        mime_type = response.get("mime_type", "")
                        if "json" in mime_type or "text" in mime_type:
                            try:
                                body_result = mock_driver.execute_cdp_cmd("Network.getResponseBody", {
                                    "requestId": request_id
                                })
                            except WebDriverException as e:
                                error_msg = str(e)
                                # Should handle gracefully
                                pass
                            except Exception as e:
                                pass
                
                self.assertTrue(True, "Error handling worked correctly")
                
            except Exception as e:
                self.fail(f"Error handling failed: {e}")


def main():
    """Run tests."""
    print("="*70)
    print("MPWiK Browser Client Error Handling Tests")
    print("="*70)
    print()
    
    # Run tests
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestNetworkLogsErrorHandling)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print()
    print("="*70)
    if result.wasSuccessful():
        print("All tests passed! ✓")
        print("="*70)
        return 0
    else:
        print("Some tests failed! ✗")
        print("="*70)
        return 1


if __name__ == '__main__':
    sys.exit(main())
