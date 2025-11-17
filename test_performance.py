#!/usr/bin/env python3
"""
Performance Testing Script for Financial Dashboard

This script helps measure and compare performance improvements.
It measures response times for various dashboard operations.

Usage:
    python test_performance.py
"""

import time
import requests
import statistics
from typing import List, Dict
import sys


def measure_response_time(url: str, num_requests: int = 5) -> Dict[str, float]:
    """
    Measure response time for multiple requests to a URL
    
    Args:
        url: URL to test
        num_requests: Number of requests to make
        
    Returns:
        Dictionary with timing statistics
    """
    times = []
    
    for i in range(num_requests):
        start = time.time()
        try:
            response = requests.get(url, timeout=30)
            elapsed = time.time() - start
            
            if response.status_code == 200:
                times.append(elapsed * 1000)  # Convert to milliseconds
                print(f"  Request {i+1}/{num_requests}: {elapsed*1000:.2f}ms")
            else:
                print(f"  Request {i+1}/{num_requests}: Failed with status {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"  Request {i+1}/{num_requests}: Error - {e}")
            continue
    
    if not times:
        return {}
    
    return {
        'min': min(times),
        'max': max(times),
        'avg': statistics.mean(times),
        'median': statistics.median(times),
        'stdev': statistics.stdev(times) if len(times) > 1 else 0
    }


def test_dashboard_performance(base_url: str = "http://localhost:5000"):
    """
    Test performance of dashboard endpoints
    
    Args:
        base_url: Base URL of the dashboard
    """
    print("=" * 60)
    print("Financial Dashboard Performance Test")
    print("=" * 60)
    print(f"\nTesting against: {base_url}\n")
    
    # Test 1: Main dashboard page
    print("Test 1: Main Dashboard Page")
    print("-" * 60)
    stats = measure_response_time(base_url, num_requests=5)
    
    if stats:
        print(f"\nResults:")
        print(f"  Min:     {stats['min']:.2f}ms")
        print(f"  Max:     {stats['max']:.2f}ms")
        print(f"  Average: {stats['avg']:.2f}ms")
        print(f"  Median:  {stats['median']:.2f}ms")
        print(f"  Std Dev: {stats['stdev']:.2f}ms")
        
        # Cache effectiveness: compare first vs subsequent requests
        improvement = ((stats['max'] - stats['min']) / stats['max']) * 100
        print(f"\n  Cache effectiveness: {improvement:.1f}% improvement")
        print(f"  (First request: {stats['max']:.2f}ms, Last request: {stats['min']:.2f}ms)")
    else:
        print("\n  ⚠️  All requests failed")
    
    print("\n")
    
    # Test 2: Health check endpoint
    print("Test 2: Health Check Endpoint")
    print("-" * 60)
    stats = measure_response_time(f"{base_url}/health", num_requests=5)
    
    if stats:
        print(f"\nResults:")
        print(f"  Average: {stats['avg']:.2f}ms")
        
        if stats['avg'] < 100:
            print(f"  ✓ Health check is fast (<100ms)")
        else:
            print(f"  ⚠️  Health check is slow (>100ms)")
    
    print("\n")
    
    # Test 3: Refresh endpoint
    print("Test 3: Data Refresh Endpoint")
    print("-" * 60)
    print("  Note: This clears cache and fetches fresh data")
    stats = measure_response_time(f"{base_url}/api/refresh", num_requests=3)
    
    if stats:
        print(f"\nResults:")
        print(f"  Average: {stats['avg']:.2f}ms")
        print(f"  (This should be slower as it fetches fresh data)")
    
    print("\n")
    
    # Summary
    print("=" * 60)
    print("Performance Test Complete")
    print("=" * 60)
    print("\nKey Metrics to Watch:")
    print("  • Dashboard loads should be <500ms after first request (cached)")
    print("  • Health check should be <100ms")
    print("  • Cache should provide 50-70% improvement on repeated requests")
    print("\nNote: These benchmarks assume database is populated and network is fast.")
    print()


def test_cache_effectiveness(base_url: str = "http://localhost:5000"):
    """
    Specifically test cache effectiveness by measuring first vs subsequent requests
    
    Args:
        base_url: Base URL of the dashboard
    """
    print("=" * 60)
    print("Cache Effectiveness Test")
    print("=" * 60)
    print(f"\nTesting against: {base_url}\n")
    
    # Clear cache first
    print("Clearing cache via refresh endpoint...")
    try:
        requests.get(f"{base_url}/api/refresh", timeout=30)
        print("  ✓ Cache cleared\n")
    except:
        print("  ⚠️  Could not clear cache\n")
    
    # Measure first request (cache miss)
    print("Request 1 (Cache Miss):")
    start = time.time()
    try:
        response = requests.get(base_url, timeout=30)
        first_time = (time.time() - start) * 1000
        print(f"  Time: {first_time:.2f}ms")
    except Exception as e:
        print(f"  Error: {e}")
        return
    
    # Wait a bit
    time.sleep(0.5)
    
    # Measure second request (cache hit)
    print("\nRequest 2 (Cache Hit):")
    start = time.time()
    try:
        response = requests.get(base_url, timeout=30)
        second_time = (time.time() - start) * 1000
        print(f"  Time: {second_time:.2f}ms")
    except Exception as e:
        print(f"  Error: {e}")
        return
    
    # Calculate improvement
    improvement = ((first_time - second_time) / first_time) * 100
    print(f"\n{'='*60}")
    print(f"Cache Performance:")
    print(f"  First Request (no cache):  {first_time:.2f}ms")
    print(f"  Second Request (cached):   {second_time:.2f}ms")
    print(f"  Improvement:               {improvement:.1f}%")
    
    if improvement > 40:
        print(f"  ✓ Cache is working effectively (>{improvement:.0f}% improvement)")
    else:
        print(f"  ⚠️  Cache improvement is lower than expected (<40%)")
    
    print()


def check_prerequisites(base_url: str = "http://localhost:5000"):
    """
    Check if dashboard is running and accessible
    
    Args:
        base_url: Base URL of the dashboard
        
    Returns:
        True if dashboard is accessible, False otherwise
    """
    print("Checking prerequisites...")
    
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("  ✓ Dashboard is running and accessible")
            data = response.json()
            if data.get('database') == 'connected':
                print("  ✓ Database connection is healthy")
            else:
                print("  ⚠️  Database connection issue")
                return False
            return True
        else:
            print(f"  ✗ Dashboard returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("  ✗ Cannot connect to dashboard")
        print(f"     Make sure Flask app is running: python app.py")
        return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


if __name__ == "__main__":
    base_url = "http://localhost:5000"
    
    # Allow custom URL from command line
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    
    # Check if dashboard is running
    if not check_prerequisites(base_url):
        print("\nPlease start the dashboard first:")
        print("  python app.py")
        sys.exit(1)
    
    print()
    
    # Run tests
    try:
        test_dashboard_performance(base_url)
        test_cache_effectiveness(base_url)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(0)
