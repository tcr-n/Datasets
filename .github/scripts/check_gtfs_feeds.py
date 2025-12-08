#!/usr/bin/env python3
"""
GTFS Feed Checker Script
Validates all GTFS feed sources from dataset.json to ensure they are accessible and valid.
"""

import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import urlparse
import urllib.request
import urllib.error

# Configuration
TIMEOUT = 15  # seconds
MAX_RETRIES = 2
DELAY_BETWEEN_CHECKS = 0.5  # seconds to avoid overwhelming servers


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def load_dataset(file_path: str = "dataset.json") -> List[Dict]:
    """Load and parse the dataset.json file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"{Colors.RED}Error: {file_path} not found{Colors.RESET}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"{Colors.RED}Error: Invalid JSON in {file_path}: {e}{Colors.RESET}")
        sys.exit(1)


def check_url(url: str, retries: int = MAX_RETRIES) -> Tuple[bool, str, int]:
    """
    Check if a URL is accessible and returns a valid response.
    
    Returns:
        Tuple of (success: bool, message: str, status_code: int)
    """
    for attempt in range(retries):
        try:
            # Create request with headers to mimic a browser
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; GTFS-Checker/1.0)',
                    'Accept': '*/*'
                }
            )
            
            with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
                status_code = response.getcode()
                content_type = response.headers.get('Content-Type', '')
                content_length = response.headers.get('Content-Length', 'unknown')
                
                # Check if response looks valid
                if status_code == 200:
                    # Read a small portion to verify it's not an error page
                    content_sample = response.read(1024)
                    
                    # Check for ZIP file signature (GTFS files are ZIP archives)
                    if content_sample[:4] == b'PK\x03\x04':
                        return True, f"OK (ZIP file, {content_length} bytes)", status_code
                    elif len(content_sample) > 0:
                        return True, f"OK ({content_type}, {content_length} bytes)", status_code
                    else:
                        return False, "Empty response", status_code
                else:
                    return False, f"HTTP {status_code}", status_code
                    
        except urllib.error.HTTPError as e:
            if attempt < retries - 1:
                time.sleep(1)
                continue
            return False, f"HTTP {e.code}: {e.reason}", e.code
            
        except urllib.error.URLError as e:
            if attempt < retries - 1:
                time.sleep(1)
                continue
            return False, f"Connection error: {str(e.reason)}", 0
            
        except TimeoutError:
            if attempt < retries - 1:
                time.sleep(1)
                continue
            return False, "Timeout", 0
            
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)
                continue
            return False, f"Error: {type(e).__name__}: {str(e)}", 0
    
    return False, "Max retries exceeded", 0


def validate_feed_structure(feed: Dict, index: int) -> Tuple[bool, List[str]]:
    """
    Validate that a feed entry has the required structure.
    
    Returns:
        Tuple of (is_valid: bool, errors: List[str])
    """
    errors = []
    required_fields = ['type', 'source', 'feedId', 'reference']
    
    for field in required_fields:
        if field not in feed:
            errors.append(f"Missing required field: {field}")
    
    if 'type' in feed and feed['type'] != 'gtfs':
        errors.append(f"Invalid type: {feed['type']} (expected 'gtfs')")
    
    if 'source' in feed:
        parsed = urlparse(feed['source'])
        if not parsed.scheme or not parsed.netloc:
            errors.append(f"Invalid source URL: {feed['source']}")
    
    if 'reference' in feed:
        parsed = urlparse(feed['reference'])
        if not parsed.scheme or not parsed.netloc:
            errors.append(f"Invalid reference URL: {feed['reference']}")
    
    return len(errors) == 0, errors


def main():
    """Main execution function"""
    print(f"{Colors.BOLD}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}GTFS Feed Checker{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*70}{Colors.RESET}\n")
    
    # Load dataset
    print(f"{Colors.BLUE}Loading dataset.json...{Colors.RESET}")
    feeds = load_dataset()
    print(f"Found {len(feeds)} feed(s) to check\n")
    
    # Statistics
    total = len(feeds)
    structure_errors = 0
    successful = 0
    failed = 0
    failed_feeds = []
    
    # Check each feed
    print(f"{Colors.BOLD}Checking feeds...{Colors.RESET}\n")
    
    for index, feed in enumerate(feeds, 1):
        feed_id = feed.get('feedId', f'feed-{index}')
        source_url = feed.get('source', 'N/A')
        
        print(f"[{index}/{total}] {Colors.BOLD}{feed_id}{Colors.RESET}")
        print(f"  Source: {source_url}")
        
        # Validate structure
        is_valid, errors = validate_feed_structure(feed, index)
        if not is_valid:
            structure_errors += 1
            print(f"  {Colors.RED}✗ Structure Error:{Colors.RESET}")
            for error in errors:
                print(f"    - {error}")
            failed_feeds.append({
                'feedId': feed_id,
                'source': source_url,
                'error': '; '.join(errors)
            })
            print()
            continue
        
        # Check URL accessibility
        success, message, status_code = check_url(source_url)
        
        if success:
            successful += 1
            print(f"  {Colors.GREEN}✓ {message}{Colors.RESET}")
        else:
            failed += 1
            print(f"  {Colors.RED}✗ {message}{Colors.RESET}")
            failed_feeds.append({
                'feedId': feed_id,
                'source': source_url,
                'error': message
            })
        
        print()
        
        # Small delay to avoid overwhelming servers
        if index < total:
            time.sleep(DELAY_BETWEEN_CHECKS)
    
    # Print summary
    print(f"{Colors.BOLD}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}Summary{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*70}{Colors.RESET}\n")
    
    print(f"Total feeds:          {total}")
    print(f"{Colors.GREEN}Successful:           {successful}{Colors.RESET}")
    print(f"{Colors.RED}Failed:               {failed}{Colors.RESET}")
    print(f"{Colors.YELLOW}Structure errors:     {structure_errors}{Colors.RESET}")
    
    success_rate = (successful / total * 100) if total > 0 else 0
    print(f"\nSuccess rate:         {success_rate:.1f}%")
    
    # List failed feeds
    if failed_feeds:
        print(f"\n{Colors.RED}{Colors.BOLD}Failed Feeds:{Colors.RESET}")
        for failed_feed in failed_feeds:
            print(f"  • {failed_feed['feedId']}")
            print(f"    URL: {failed_feed['source']}")
            print(f"    Error: {failed_feed['error']}")
            print()
    
    print(f"{Colors.BOLD}{'='*70}{Colors.RESET}\n")
    
    # Exit with appropriate code
    if failed > 0 or structure_errors > 0:
        print(f"{Colors.RED}Check failed! Please review the errors above.{Colors.RESET}")
        sys.exit(1)
    else:
        print(f"{Colors.GREEN}All feeds are accessible!{Colors.RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
