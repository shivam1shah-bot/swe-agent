#!/usr/bin/env python3
"""
Upload Code Review Metrics to API

This script uploads collected repository metrics to the code review API endpoint.
It processes extracted metrics files and uploads them with proper authentication and retry logic.
"""

import os
import json
import glob
import time
import argparse
import requests
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path


class MetricsUploader:
    """Handles uploading repository metrics to the API with retry logic and error handling."""
    
    def __init__(self, api_base_url: str, auth_token: Optional[str] = None):
        """
        Initialize the uploader with API configuration.
        
        Args:
            api_base_url: Base URL for the API (e.g., "http://localhost:28001")
            auth_token: Authentication token for admin access
        """
        self.api_base_url = api_base_url.rstrip('/')
        self.auth_token = auth_token
        self.upload_endpoint = f"{self.api_base_url}/api/v1/code-review/repository-metrics"
        self.session = requests.Session()
        
        # Set up authentication headers
        if self.auth_token:
            # Parse username:password format
            if ':' in self.auth_token:
                username, password = self.auth_token.split(':', 1)
                self.session.auth = (username, password)
            else:
                self.session.headers.update({
                    "Authorization": f"Bearer {self.auth_token}"
                })
            
            self.session.headers.update({
                "Content-Type": "application/json"
            })
    
    def find_extracted_metrics_files(self, date: str) -> List[Tuple[str, str]]:
        """
        Find all extracted metrics files for a specific date.
        
        Args:
            date: Date in YYYY-MM-DD format
            
        Returns:
            List of tuples (file_path, repository_name)
        """
        metrics_dir = f"uploads/metrics/extracted/{date}"
        pattern = f"{metrics_dir}/razorpay-*-metrics.json"
        
        files = glob.glob(pattern)
        if not files:
            print(f"❌ No metrics files found in {metrics_dir}")
            return []
        
        # Extract repository names from filenames
        repo_files = []
        for file_path in files:
            filename = Path(file_path).name
            # Extract repo name: razorpay-[repo-name]-metrics.json -> razorpay/[repo-name]
            if filename.startswith('razorpay-') and filename.endswith('-metrics.json'):
                repo_part = filename[9:-13]  # Remove 'razorpay-' prefix (9 chars) and '-metrics.json' suffix (13 chars)
                repo_name = f"razorpay/{repo_part}"  # Keep dashes in repo names
                repo_files.append((file_path, repo_name))
        
        print(f"📁 Found {len(repo_files)} metrics files for {date}")
        for _, repo in repo_files:
            print(f"   • {repo}")
        
        return repo_files
    
    def validate_metrics_file(self, file_path: str) -> Tuple[bool, Optional[Dict]]:
        """
        Validate and load metrics file.
        
        Args:
            file_path: Path to the metrics JSON file
            
        Returns:
            Tuple of (is_valid, metrics_data)
        """
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Basic validation - check required top-level keys
            required_keys = ['metadata', 'stats', 'effectiveness', 'productivity', 'technical']
            if not all(key in data for key in required_keys):
                print(f"❌ Missing required keys in {file_path}")
                return False, None
            
            # Validate metadata has required fields
            metadata = data.get('metadata', {})
            if not all(key in metadata for key in ['date', 'repository', 'generated_at', 'version']):
                print(f"❌ Invalid metadata in {file_path}")
                return False, None
            
            return True, data
            
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in {file_path}: {e}")
            return False, None
        except Exception as e:
            print(f"❌ Error reading {file_path}: {e}")
            return False, None
    
    def upload_single_repository(self, repo_name: str, date: str, metrics_data: Dict, max_attempts: int = 3) -> bool:
        """
        Upload metrics for a single repository with retry logic.
        
        Args:
            repo_name: Repository name (e.g., "razorpay/pg-router")
            date: Date in YYYY-MM-DD format
            metrics_data: Complete metrics data
            max_attempts: Maximum retry attempts
            
        Returns:
            True if upload successful, False otherwise
        """
        payload = {
            "repository": repo_name,
            "date": date,
            "metrics": metrics_data
        }
        
        print(f"📤 Uploading {repo_name} for {date}...")
        
        for attempt in range(1, max_attempts + 1):
            try:
                print(f"   🔄 Attempt {attempt}/{max_attempts}")
                
                response = self.session.post(
                    self.upload_endpoint,
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 200 or response.status_code == 201:
                    result = response.json()
                    if result.get('success', False):
                        print(f"   ✅ Success: {repo_name}")
                        return True
                    else:
                        print(f"   ❌ API returned success=false: {result.get('message', 'Unknown error')}")
                else:
                    print(f"   ❌ HTTP {response.status_code}: {response.text}")
                
            except requests.exceptions.Timeout:
                print(f"   ⏱️ Timeout on attempt {attempt}")
            except requests.exceptions.ConnectionError:
                print(f"   🔌 Connection error on attempt {attempt}")
            except requests.exceptions.RequestException as e:
                print(f"   ❌ Request error on attempt {attempt}: {e}")
            except Exception as e:
                print(f"   ❌ Unexpected error on attempt {attempt}: {e}")
            
            # Wait before retry (except on last attempt)
            if attempt < max_attempts:
                wait_time = attempt * 2  # Exponential backoff: 2s, 4s, 6s
                print(f"   ⏳ Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
        
        print(f"   ❌ Failed: {repo_name} (all {max_attempts} attempts failed)")
        return False
    
    def upload_all_repositories(self, date: str, max_attempts: int = 3) -> Dict[str, bool]:
        """
        Upload metrics for all repositories found for the specified date.
        
        Args:
            date: Date in YYYY-MM-DD format
            max_attempts: Maximum retry attempts per repository
            
        Returns:
            Dictionary mapping repository names to success status
        """
        repo_files = self.find_extracted_metrics_files(date)
        if not repo_files:
            return {}
        
        results = {}
        total = len(repo_files)
        
        print(f"\n🚀 Starting upload process for {total} repositories...")
        print(f"📡 API Endpoint: {self.upload_endpoint}")
        print(f"📅 Date: {date}")
        print(f"🔄 Max attempts per repo: {max_attempts}")
        print("=" * 60)
        
        for i, (file_path, repo_name) in enumerate(repo_files, 1):
            print(f"\n📊 Processing {i}/{total}: {repo_name}")
            
            # Validate file
            is_valid, metrics_data = self.validate_metrics_file(file_path)
            if not is_valid:
                results[repo_name] = False
                print(f"   ❌ Skipped due to validation errors")
                continue
            
            # Upload with retries
            success = self.upload_single_repository(repo_name, date, metrics_data, max_attempts)
            results[repo_name] = success
        
        return results
    
    def generate_summary_report(self, results: Dict[str, bool]) -> None:
        """
        Generate and display a summary report of upload results.
        
        Args:
            results: Dictionary mapping repository names to success status
        """
        if not results:
            print("\n📋 No repositories processed.")
            return
        
        successful = [repo for repo, success in results.items() if success]
        failed = [repo for repo, success in results.items() if not success]
        
        print("\n" + "=" * 60)
        print("📋 UPLOAD SUMMARY REPORT")
        print("=" * 60)
        
        print(f"📊 Total Repositories: {len(results)}")
        print(f"✅ Successful Uploads: {len(successful)}")
        print(f"❌ Failed Uploads: {len(failed)}")
        print(f"📈 Success Rate: {(len(successful) / len(results)) * 100:.1f}%")
        
        if successful:
            print(f"\n✅ SUCCESSFUL UPLOADS ({len(successful)}):")
            for repo in successful:
                print(f"   • {repo}")
        
        if failed:
            print(f"\n❌ FAILED UPLOADS ({len(failed)}):")
            for repo in failed:
                print(f"   • {repo}")
        
        print("\n🎯 Upload process completed!")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Upload repository metrics to the code review API",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--date",
        required=True,
        help="Date of metrics to upload (YYYY-MM-DD format)"
    )
    
    parser.add_argument(
        "--api-url",
        default="http://localhost:28001",
        help="Base URL for the API (default: http://localhost:28001)"
    )
    
    parser.add_argument(
        "--auth-token",
        default=None,
        help="Authentication token for admin access (or set ADMIN_AUTH_TOKEN env var)"
    )
    
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=3,
        help="Maximum retry attempts per repository (default: 3)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate files without uploading"
    )
    
    args = parser.parse_args()
    
    # Get authentication token
    auth_token = args.auth_token or os.getenv('ADMIN_AUTH_TOKEN')
    if not auth_token and not args.dry_run:
        print("⚠️ No authentication token provided!")
        print("Use --auth-token argument or set ADMIN_AUTH_TOKEN environment variable")
        return
    
    # Initialize uploader
    uploader = MetricsUploader(args.api_url, auth_token)
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - Validating files only")
        repo_files = uploader.find_extracted_metrics_files(args.date)
        
        for file_path, repo_name in repo_files:
            is_valid, _ = uploader.validate_metrics_file(file_path)
            status = "✅ Valid" if is_valid else "❌ Invalid"
            print(f"   {status}: {repo_name}")
        
        return
    
    # Upload metrics
    results = uploader.upload_all_repositories(args.date, args.max_attempts)
    
    # Generate summary report
    uploader.generate_summary_report(results)


if __name__ == "__main__":
    main()
