#!/usr/bin/env python3
"""
Realtime Feed Checker Script
Validates all realtime feed sources from realtime.json to ensure they are accessible and valid.
"""

import json
import sys
import time
import os
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request
import urllib.error

# Configuration
TIMEOUT = 15  # seconds
MAX_RETRIES = 2
MAX_WORKERS = 20  # Number of concurrent checks
RATE_LIMIT_DELAY = 0.1  # Small delay between batches


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def load_realtime_data(file_path: str = "realtime.json") -> Dict:
    """Load and parse the realtime.json file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Replace API key placeholders with environment variables
        jp_api_key = os.environ.get('JP_API_KEY', '')
        jp_challenge_api_key = os.environ.get('JP_CHALLENGE_API_KEY', '')
        
        content = content.replace('{{{JP_API_KEY}}}', jp_api_key)
        content = content.replace('{{{JP_CHALLENGE_API_KEY}}}', jp_challenge_api_key)
        
        return json.loads(content)
    except FileNotFoundError:
        print(f"{Colors.RED}Error: {file_path} not found{Colors.RESET}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"{Colors.RED}Error: Invalid JSON in {file_path}: {e}{Colors.RESET}")
        sys.exit(1)


def check_url(url: str, retries: int = MAX_RETRIES) -> Tuple[bool, str, int]:
    """
    Check if a URL is accessible and returns a valid response.
    For realtime APIs, uses GET request as many don't support HEAD.
    
    Returns:
        Tuple of (success: bool, message: str, status_code: int)
    """
    for attempt in range(retries):
        try:
            # For realtime feeds, always use GET as APIs often don't support HEAD
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; Realtime-Checker/1.0)',
                    'Accept': 'application/x-protobuf, application/json, */*'
                }
            )
            
            with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
                status_code = response.getcode()
                content_type = response.headers.get('Content-Type', '')
                content_length = response.headers.get('Content-Length', 'unknown')
                
                # 200 OK - normal success
                if status_code == 200:
                    # Read a small sample to verify it's not an error page
                    content_sample = response.read(1024)
                    
                    # Check if we got actual data
                    if len(content_sample) > 0:
                        # Check for protobuf (GTFS-RT) or JSON
                        is_protobuf = content_sample[0:2] in [b'\x0a', b'\x12', b'\x1a']  # Common protobuf starters
                        is_json = content_sample.strip().startswith(b'{') or content_sample.strip().startswith(b'[')
                        
                        if is_protobuf:
                            return True, f"OK (GTFS-RT protobuf, {content_length} bytes)", status_code
                        elif is_json:
                            return True, f"OK (JSON, {content_length} bytes)", status_code
                        else:
                            return True, f"OK ({content_type}, {content_length} bytes)", status_code
                    else:
                        return False, "Empty response", status_code
                # 204 No Content - valid for realtime feeds with no current updates
                elif status_code == 204:
                    return True, f"OK (No Content - no updates available)", status_code
                # 429 Too Many Requests - endpoint exists but is rate limited
                elif status_code == 429:
                    return True, f"OK (Rate limited - endpoint is working)", status_code
                else:
                    return False, f"HTTP {status_code}", status_code
                    
        except urllib.error.HTTPError as e:
            # Treat 429 (rate limit) as success - means endpoint is working
            if e.code == 429:
                return True, f"OK (Rate limited - endpoint is working)", e.code
            
            if attempt < retries - 1:
                time.sleep(0.5)
                continue
            return False, f"HTTP {e.code}: {e.reason}", e.code
            
        except urllib.error.URLError as e:
            if attempt < retries - 1:
                time.sleep(0.5)
                continue
            return False, f"Connection error: {str(e.reason)}", 0
            
        except TimeoutError:
            if attempt < retries - 1:
                time.sleep(0.5)
                continue
            return False, "Timeout", 0
            
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(0.5)
                continue
            return False, f"Error: {type(e).__name__}: {str(e)}", 0
    
    return False, "Max retries exceeded", 0


def validate_updater_structure(updater: Dict, index: int) -> Tuple[bool, List[str]]:
    """
    Validate that an updater entry has the required structure.
    
    Returns:
        Tuple of (is_valid: bool, errors: List[str])
    """
    errors = []
    required_fields = ['type', 'url', 'feedId']
    
    for field in required_fields:
        if field not in updater:
            errors.append(f"Missing required field: {field}")
    
    # Validate updater type - support both hyphen and underscore variants
    valid_types = [
        'gtfs-http', 'gtfs_http',
        'stop-time-updater', 'stop_time_updater',
        'vehicle-positions', 'vehicle_positions',
        'trip-updates', 'trip_updates',
        'vehicle-parking-updater', 'vehicle_parking_updater',
        'bike-rental-updater', 'bike_rental_updater',
        'bike-park-updater', 'bike_park_updater',
        'real-time-alerts', 'real_time_alerts',
        'alerts', 'alert'
    ]
    if 'type' in updater and updater['type'] not in valid_types:
        errors.append(f"Invalid type: {updater['type']} (expected valid OTP updater type)")
    
    # Validate URL
    if 'url' in updater:
        parsed = urlparse(updater['url'])
        if not parsed.scheme or not parsed.netloc:
            errors.append(f"Invalid URL: {updater['url']}")
    
    return len(errors) == 0, errors


def check_updater(updater: Dict, index: int, total: int) -> Dict:
    """
    Check a single realtime updater (structure validation + URL check).
    Returns a dict with results.
    """
    updater_type = updater.get('type', 'unknown')
    feed_id = updater.get('feedId', 'unknown')
    url = updater.get('url', 'N/A')
    
    result = {
        'index': index,
        'type': updater_type,
        'feedId': feed_id,
        'url': url,
        'structure_valid': True,
        'structure_errors': [],
        'url_success': False,
        'url_message': '',
        'status_code': 0
    }
    
    # Validate structure
    is_valid, errors = validate_updater_structure(updater, index)
    result['structure_valid'] = is_valid
    result['structure_errors'] = errors
    
    if not is_valid:
        return result
    
    # Check URL accessibility
    success, message, status_code = check_url(url)
    result['url_success'] = success
    result['url_message'] = message
    result['status_code'] = status_code
    
    return result


def main():
    """Main execution function"""
    print(f"{Colors.BOLD}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}Realtime Feed Checker{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*70}{Colors.RESET}\n")
    
    # Load realtime data
    print(f"{Colors.BLUE}Loading realtime.json...{Colors.RESET}")
    realtime_data = load_realtime_data()
    
    if 'updaters' not in realtime_data:
        print(f"{Colors.RED}Error: No 'updaters' field found in realtime.json{Colors.RESET}")
        sys.exit(1)
    
    updaters = realtime_data['updaters']
    print(f"Found {len(updaters)} realtime updater(s) to check\n")
    
    # Statistics
    total = len(updaters)
    structure_errors = 0
    successful = 0
    failed = 0
    failed_updaters = []
    
    # Check updaters concurrently
    print(f"{Colors.BOLD}Checking realtime updaters concurrently (max {MAX_WORKERS} workers)...{Colors.RESET}\n")
    
    start_time = time.time()
    results = []
    
    # Use ThreadPoolExecutor for concurrent checks
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all tasks
        future_to_updater = {
            executor.submit(check_updater, updater, index, total): (updater, index) 
            for index, updater in enumerate(updaters, 1)
        }
        
        # Process results as they complete
        completed = 0
        for future in as_completed(future_to_updater):
            result = future.result()
            results.append(result)
            completed += 1
            
            # Print progress indicator
            if completed % 10 == 0 or completed == total:
                print(f"Progress: {completed}/{total} updaters checked", end='\r')
    
    print(f"\nCompleted in {time.time() - start_time:.2f} seconds\n")
    
    # Sort results by index to display in order
    results.sort(key=lambda x: x['index'])
    
    # Print detailed results
    print(f"{Colors.BOLD}Results:{Colors.RESET}\n")
    for result in results:
        print(f"[{result['index']}/{total}] {Colors.BOLD}{result['type']}{Colors.RESET} - {result['feedId']}")
        print(f"  URL: {result['url']}")
        
        if not result['structure_valid']:
            structure_errors += 1
            print(f"  {Colors.RED}✗ Structure Error:{Colors.RESET}")
            for error in result['structure_errors']:
                print(f"    - {error}")
            failed_updaters.append({
                'type': result['type'],
                'feedId': result['feedId'],
                'url': result['url'],
                'error': '; '.join(result['structure_errors'])
            })
        elif result['url_success']:
            successful += 1
            print(f"  {Colors.GREEN}✓ {result['url_message']}{Colors.RESET}")
        else:
            failed += 1
            print(f"  {Colors.RED}✗ {result['url_message']}{Colors.RESET}")
            failed_updaters.append({
                'type': result['type'],
                'feedId': result['feedId'],
                'url': result['url'],
                'error': result['url_message']
            })
        
        print()
    
    # Print summary
    print(f"{Colors.BOLD}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}Summary{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*70}{Colors.RESET}\n")
    
    print(f"Total updaters:       {total}")
    print(f"{Colors.GREEN}Successful:           {successful}{Colors.RESET}")
    print(f"{Colors.RED}Failed:               {failed}{Colors.RESET}")
    print(f"{Colors.YELLOW}Structure errors:     {structure_errors}{Colors.RESET}")
    
    success_rate = (successful / total * 100) if total > 0 else 0
    print(f"\nSuccess rate:         {success_rate:.1f}%")
    
    # List failed updaters
    if failed_updaters:
        print(f"\n{Colors.RED}{Colors.BOLD}Failed Updaters:{Colors.RESET}")
        for failed_updater in failed_updaters:
            print(f"  • {failed_updater['type']} - {failed_updater['feedId']}")
            print(f"    URL: {failed_updater['url']}")
            print(f"    Error: {failed_updater['error']}")
            print()
    
    print(f"{Colors.BOLD}{'='*70}{Colors.RESET}\n")
    
    # Exit with appropriate code
    if failed > 0 or structure_errors > 0:
        print(f"{Colors.RED}Check failed! Please review the errors above.{Colors.RESET}")
        sys.exit(1)
    else:
        print(f"{Colors.GREEN}All realtime updaters are accessible!{Colors.RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
