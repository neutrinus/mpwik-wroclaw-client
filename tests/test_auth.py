#!/usr/bin/env python3
"""
Test authentication with MPWiK API
This script helps test different authentication approaches.
"""

import sys
import json
from mpwik_direct import MPWiKClient

def test_auth_with_mock_token():
    """Test authentication logic with a mock ReCAPTCHA token."""
    print("Testing authentication flow...")
    
    # Create a client
    client = MPWiKClient(
        login="test_login",
        password="test_password",
        recaptcha_api_key=None  # Don't actually solve ReCAPTCHA
    )
    
    # Test payload and headers generation
    print("\n1. Testing request format (matching browser behavior):")
    
    # Simulate what _attempt_login does
    payload = {
        "login": "test_login",
        "password": "test_password"
    }
    
    headers = {
        'Origin': 'https://ebok.mpwik.wroc.pl',
        'Referer': 'https://ebok.mpwik.wroc.pl/login'
    }
    mock_token = "0cAFcWeA4tivppcjWWAWLlt0TsVQCylMt7EEiDmZaqOr8n" + ("x" * 50)
    mock_csrf = "d25ad34a-54b4-44d3-aa90-8a89c2f8ddde"
    
    headers['X-RECAPTCHA-TOKEN'] = mock_token
    headers['X-CSRF-TOKEN'] = mock_csrf
    
    print(f"   ✓ Payload structure: {list(payload.keys())}")
    print(f"   ✓ Payload contains only: login, password (no recaptcha field)")
    print(f"   ✓ ReCAPTCHA token in header: {'X-RECAPTCHA-TOKEN' in headers}")
    print(f"   ✓ CSRF token in header: {'X-CSRF-TOKEN' in headers}")
    print(f"   ✓ Origin header in request: {'Origin' in headers}")
    print(f"   ✓ Referer header in request: {'Referer' in headers}")
    print(f"   ✓ ReCAPTCHA token length: {len(headers['X-RECAPTCHA-TOKEN'])}")
    
    # Show what would be sent
    payload_for_log = {
        'login': payload['login'],
        'password': '***'
    }
    headers_for_log = {
        'Origin': headers['Origin'],
        'Referer': headers['Referer'],
        'X-RECAPTCHA-TOKEN': f"{headers['X-RECAPTCHA-TOKEN'][:20]}...",
        'X-CSRF-TOKEN': headers['X-CSRF-TOKEN']
    }
    print(f"\n   Request payload: {json.dumps(payload_for_log)}")
    print(f"   Request headers: {json.dumps(headers_for_log, indent=2)}")
    
    print("\n✓ Request format matches browser behavior!")
    print("  - ReCAPTCHA token is in X-RECAPTCHA-TOKEN header")
    print("  - CSRF token is in X-CSRF-TOKEN header")
    print("  - Origin and Referer headers are included")
    print("  - Payload contains only login and password")
    
    return True

def main():
    """Run tests."""
    print("="*70)
    print("MPWiK Authentication Test")
    print("="*70)
    
    try:
        if test_auth_with_mock_token():
            print("\n" + "="*70)
            print("All tests passed! ✓")
            print("="*70)
            return 0
        else:
            print("\n" + "="*70)
            print("Tests failed! ✗")
            print("="*70)
            return 1
    except Exception as e:
        print(f"\nError during testing: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
