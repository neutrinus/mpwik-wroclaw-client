#!/usr/bin/env python3
"""
MPWiK Wrocław CLI Client
Main command-line interface for fetching water consumption data from MPWiK Wrocław e-BOK system.
"""

import logging
import json
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Fetch water consumption data from MPWiK Wrocław'
    )
    parser.add_argument('--login', required=True, help='Login (podmiot ID)')
    parser.add_argument('--password', required=True, help='Password')
    parser.add_argument('--podmiot-id', required=False, help='Podmiot ID (defaults to login if not provided)')
    parser.add_argument('--punkt-sieci', help='Network point ID. If not provided, the first available network point will be used automatically.')
    parser.add_argument(
        '--list-punkty-sieci',
        action='store_true',
        help='List all available network points (meters) for this account'
    )
    parser.add_argument(
        '--type',
        choices=['daily', 'hourly', 'both'],
        default='daily',
        help='Type of readings to fetch'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='Number of days to fetch for daily readings (default: 7). Ignored for hourly readings which fetch today only by default.'
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
        '--method',
        type=str,
        choices=['direct', 'selenium', 'playwright'],
        default='selenium',
        help="The connection method to use: 'direct' (API), 'selenium', or 'playwright' (browser automation). Default: selenium"
    )
    parser.add_argument(
        '--headless',
        action='store_true',
        default=True,
        help='Run browser in headless mode when using browser automation methods (default: True)'
    )
    parser.add_argument(
        '--no-headless',
        action='store_true',
        help='Run browser with visible window when using browser automation methods (for manual reCAPTCHA solving)'
    )
    parser.add_argument(
        '--log-dir',
        help='Directory to save browser logs and screenshots when using browser automation methods (default: ./logs)'
    )
    parser.add_argument(
        '--capmonster-api-key',
        help='CapMonster API key for ReCAPTCHA solving (optional, for API mode)'
    )
    parser.add_argument(
        '--recaptcha-version',
        type=int,
        choices=[2, 3],
        help='Preferred ReCAPTCHA version (2 or 3). If not specified, tries v3 first then v2 as fallback'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()
    
    # Default podmiot_id to login if not provided
    if not args.podmiot_id:
        args.podmiot_id = args.login
        logger.info(f"No --podmiot-id provided, using login value: {args.podmiot_id}")
    
    # Set logging level based on debug flag
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    # Parse dates
    if args.date_from:
        date_from = datetime.strptime(args.date_from, '%Y-%m-%d').replace(
            hour=0, minute=0, second=0
        )
        # For hourly readings, if date_from is specified but date_to is not,
        # automatically set date_to to the same day to avoid API errors
        if args.type == 'hourly' and not args.date_to:
            date_to = date_from.replace(hour=23, minute=59, second=59)
            logger.info(f"Hourly readings: Using single day {date_from.strftime('%Y-%m-%d')}")
        elif args.date_to:
            date_to = datetime.strptime(args.date_to, '%Y-%m-%d').replace(
                hour=23, minute=59, second=59
            )
        else:
            date_to = datetime.now().replace(hour=23, minute=59, second=59)
    else:
        # No date_from specified
        if args.date_to:
            date_to = datetime.strptime(args.date_to, '%Y-%m-%d').replace(
                hour=23, minute=59, second=59
            )
        else:
            date_to = datetime.now().replace(hour=23, minute=59, second=59)
        
        # For hourly readings, default to yesterday only (1 day back) because
        # hourly data is not available for the current day
        # The API rejects requests for more than 1 day of hourly data
        # For daily readings, use the --days parameter (default 7)
        if args.type == 'hourly':
            # For hourly: yesterday only (from 00:00:00 yesterday to 23:59:59 yesterday)
            date_to = (datetime.now() - timedelta(days=1)).replace(hour=23, minute=59, second=59)
            date_from = date_to.replace(hour=0, minute=0, second=0)
        else:
            # For daily: use --days parameter
            date_from = (date_to - timedelta(days=args.days)).replace(
                hour=0, minute=0, second=0
            )
    
    # Validation: For hourly readings, ensure both dates are the same day
    if args.type == 'hourly':
        if date_from.date() != date_to.date():
            logger.error(f"Hourly readings require single day request. Got: {date_from.date()} to {date_to.date()}")
            logger.error("For hourly data, use: --date-from YYYY-MM-DD (without --date-to)")
            logger.error("Or specify same day for both: --date-from YYYY-MM-DD --date-to YYYY-MM-DD")
            return 1
        logger.info(f"Fetching hourly readings for: {date_from.strftime('%Y-%m-%d')}")
    
    # Choose client based on --method argument
    if args.method in ['selenium', 'playwright']:
        # Use browser automation
        if args.method == 'selenium':
            try:
                from mpwik_selenium import MPWiKBrowserClient
            except ImportError:
                logger.error("Selenium client not available. Install Selenium: uv sync --extra selenium")
                return 1
            
            logger.info("Using Selenium browser automation mode")
            headless = args.headless and not args.no_headless
            
            with MPWiKBrowserClient(
                login=args.login,
                password=args.password,
                headless=headless,
                log_dir=args.log_dir,
                debug=args.debug
            ) as client:
                if not client.authenticate():
                    logger.error("Authentication failed. Exiting.")
                    return 1
                
                # Handle list punkty sieci request
                if args.list_punkty_sieci:
                    # Use browser client's get_punkty_sieci method
                    punkty = client.get_punkty_sieci(args.podmiot_id)
                    if punkty:
                        # Use MPWiKClient for formatting only
                        from mpwik_direct import MPWiKClient
                        api_client = MPWiKClient(args.login, args.password)
                        api_client.print_punkty_sieci(punkty)
                        
                        # Save to file if requested
                        if args.output:
                            try:
                                with open(args.output, 'w', encoding='utf-8') as f:
                                    json.dump({'punkty': punkty}, f, indent=2, ensure_ascii=False)
                                logger.info(f"Network points saved to {args.output}")
                            except Exception as e:
                                logger.error(f"Failed to save network points: {e}")
                    logger.info(f"Browser logs saved to: {client.log_dir}")
                    return 0
                
                # Auto-fetch punkt-sieci if not provided
                punkt_sieci = args.punkt_sieci
                if not punkt_sieci:
                    logger.info("No --punkt-sieci provided, fetching available network points...")
                    punkty = client.get_punkty_sieci(args.podmiot_id)
                    if punkty and len(punkty) > 0:
                        # Use the first available punkt-sieci
                        # Convert format from '0123/2021' to '0123-2021' for API compatibility
                        punkt_sieci = punkty[0].get('numer', '').replace('/', '-')
                        logger.info(f"Using first available network point: {punkt_sieci}")
                        logger.info(f"Address: {punkty[0].get('adres', 'N/A')}")
                    else:
                        logger.error("No network points available for this account")
                        return 1
                
                results = {}
                
                # Fetch daily readings
                if args.type in ['daily', 'both']:
                    daily_readings = client.get_daily_readings(
                        args.podmiot_id,
                        punkt_sieci,
                        date_from,
                        date_to
                    )
                    
                    if daily_readings:
                        # Use the print_readings method from MPWiKClient
                        from mpwik_direct import MPWiKClient
                        api_client = MPWiKClient(args.login, args.password)
                        api_client.print_readings(daily_readings, "daily")
                        results['daily'] = daily_readings
                
                # Fetch hourly readings
                if args.type in ['hourly', 'both']:
                    # For hourly, limit to smaller time ranges to avoid too much data
                    if args.type == 'hourly':
                        hourly_date_from = date_from
                        hourly_date_to = date_to
                    else:
                        # If fetching both, only get hourly for last day
                        hourly_date_from = date_to.replace(hour=0, minute=0, second=0)
                        hourly_date_to = date_to
                    
                    hourly_readings = client.get_hourly_readings(
                        args.podmiot_id,
                        punkt_sieci,
                        hourly_date_from,
                        hourly_date_to
                    )
                    
                    if hourly_readings:
                        # Use the print_readings method from MPWiKClient
                        from mpwik_direct import MPWiKClient
                        api_client = MPWiKClient(args.login, args.password)
                        api_client.print_readings(hourly_readings, "hourly")
                        results['hourly'] = hourly_readings
                
                # Save to file if requested
                if args.output:
                    try:
                        with open(args.output, 'w', encoding='utf-8') as f:
                            json.dump(results, f, indent=2, ensure_ascii=False)
                        logger.info(f"Results saved to {args.output}")
                    except Exception as e:
                        logger.error(f"Failed to save results: {e}")
                
                logger.info(f"Browser logs saved to: {client.log_dir}")
        
        elif args.method == 'playwright':
            try:
                from mpwik_playwright import MPWikPlaywrightClient
            except ImportError:
                logger.error("Playwright client not available. Install Playwright: uv sync --extra playwright && playwright install")
                return 1
            
            logger.info("Using Playwright browser automation mode")
            headless = args.headless and not args.no_headless
            
            with MPWikPlaywrightClient(
                login=args.login,
                password=args.password,
                headless=headless,
                browser_type='chromium'
            ) as client:
                client.login_and_establish_session()
                
                # Handle list punkty sieci request
                if args.list_punkty_sieci:
                    # Use playwright client's get_points method
                    punkty = client.get_points()
                    if punkty:
                        # Use MPWiKClient for formatting only
                        from mpwik_direct import MPWiKClient
                        api_client = MPWiKClient(args.login, args.password)
                        api_client.print_punkty_sieci(punkty)
                        
                        # Save to file if requested
                        if args.output:
                            try:
                                with open(args.output, 'w', encoding='utf-8') as f:
                                    json.dump({'punkty': punkty}, f, indent=2, ensure_ascii=False)
                                logger.info(f"Network points saved to {args.output}")
                            except Exception as e:
                                logger.error(f"Failed to save network points: {e}")
                    return 0
                
                # Auto-fetch punkt-sieci if not provided
                punkt_sieci = args.punkt_sieci
                if not punkt_sieci:
                    logger.info("No --punkt-sieci provided, fetching available network points...")
                    punkty = client.get_points()
                    if punkty and len(punkty) > 0:
                        # Use the first available punkt-sieci
                        # Convert format from '0123/2021' to '0123-2021' for API compatibility
                        punkt_sieci = punkty[0].get('numer', '').replace('/', '-')
                        logger.info(f"Using first available network point: {punkt_sieci}")
                        logger.info(f"Address: {punkty[0].get('adres', 'N/A')}")
                    else:
                        logger.error("No network points available for this account")
                        return 1
                
                results = {}
                
                # Fetch daily or hourly readings
                if args.type in ['daily', 'both']:
                    daily_readings = client.get_readings(
                        punkt_sieci,
                        'dobowe',
                        date_from,
                        date_to
                    )
                    
                    if daily_readings:
                        # Use the print_readings method from MPWiKClient
                        from mpwik_direct import MPWiKClient
                        api_client = MPWiKClient(args.login, args.password)
                        api_client.print_readings(daily_readings, "daily")
                        results['daily'] = daily_readings
                
                # Fetch hourly readings
                if args.type in ['hourly', 'both']:
                    # For hourly, limit to smaller time ranges to avoid too much data
                    if args.type == 'hourly':
                        hourly_date_from = date_from
                        hourly_date_to = date_to
                    else:
                        # If fetching both, only get hourly for last day
                        hourly_date_from = date_to.replace(hour=0, minute=0, second=0)
                        hourly_date_to = date_to
                    
                    hourly_readings = client.get_readings(
                        punkt_sieci,
                        'godzinowe',
                        hourly_date_from,
                        hourly_date_to
                    )
                    
                    if hourly_readings:
                        # Use the print_readings method from MPWiKClient
                        from mpwik_direct import MPWiKClient
                        api_client = MPWiKClient(args.login, args.password)
                        api_client.print_readings(hourly_readings, "hourly")
                        results['hourly'] = hourly_readings
                
                # Save to file if requested
                if args.output:
                    try:
                        with open(args.output, 'w', encoding='utf-8') as f:
                            json.dump(results, f, indent=2, ensure_ascii=False)
                        logger.info(f"Results saved to {args.output}")
                    except Exception as e:
                        logger.error(f"Failed to save results: {e}")
    
    else:  # args.method == 'direct'
        # Use API mode
        logger.info("Using API mode")
        
        from mpwik_direct import MPWiKClient
        
        # Create client and authenticate
        client = MPWiKClient(
            args.login, 
            args.password, 
            args.capmonster_api_key,
            args.recaptcha_version,
            debug=args.debug,
            log_dir=args.log_dir
        )
        
        if not client.authenticate():
            logger.error("Authentication failed. Exiting.")
            return 1
        
        # Handle list punkty sieci request
        if args.list_punkty_sieci:
            punkty = client.get_punkty_sieci(args.podmiot_id)
            if punkty:
                client.print_punkty_sieci(punkty)
                
                # Save to file if requested
                if args.output:
                    try:
                        with open(args.output, 'w', encoding='utf-8') as f:
                            json.dump({'punkty': punkty}, f, indent=2, ensure_ascii=False)
                        logger.info(f"Network points saved to {args.output}")
                    except Exception as e:
                        logger.error(f"Failed to save network points: {e}")
            return 0
        
        # Auto-fetch punkt-sieci if not provided
        punkt_sieci = args.punkt_sieci
        if not punkt_sieci:
            logger.info("No --punkt-sieci provided, fetching available network points...")
            punkty = client.get_punkty_sieci(args.podmiot_id)
            if punkty and len(punkty) > 0:
                # Use the first available punkt-sieci
                # Convert format from '0123/2021' to '0123-2021' for API compatibility
                punkt_sieci = punkty[0].get('numer', '').replace('/', '-')
                logger.info(f"Using first available network point: {punkt_sieci}")
                logger.info(f"Address: {punkty[0].get('adres', 'N/A')}")
            else:
                logger.error("No network points available for this account")
                return 1
        
        results = {}
        
        # Fetch daily readings
        if args.type in ['daily', 'both']:
            daily_readings = client.get_daily_readings(
                args.podmiot_id,
                punkt_sieci,
                date_from,
                date_to
            )
            
            if daily_readings:
                client.print_readings(daily_readings, "daily")
                results['daily'] = daily_readings
        
        # Fetch hourly readings
        if args.type in ['hourly', 'both']:
            # For hourly, limit to smaller time ranges to avoid too much data
            if args.type == 'hourly':
                hourly_date_from = date_from
                hourly_date_to = date_to
            else:
                # If fetching both, only get hourly for last day
                hourly_date_from = date_to.replace(hour=0, minute=0, second=0)
                hourly_date_to = date_to
            
            hourly_readings = client.get_hourly_readings(
                args.podmiot_id,
                punkt_sieci,
                hourly_date_from,
                hourly_date_to
            )
            
            if hourly_readings:
                client.print_readings(hourly_readings, "hourly")
                results['hourly'] = hourly_readings
        
        # Save to file if requested
        if args.output:
            try:
                with open(args.output, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)
                logger.info(f"Results saved to {args.output}")
            except Exception as e:
                logger.error(f"Failed to save results: {e}")
    
    return 0


if __name__ == '__main__':
    exit(main())
