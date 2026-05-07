#!/usr/bin/env python3
"""
Auto-retry script for repositories that failed due to GitHub rate limits.
Retries every 10 minutes until successful or max attempts reached.
"""

import subprocess
import time
import sys
from datetime import datetime

def try_collect_repo(repo_name: str, date: str) -> bool:
    """Try to collect data for a repository. Returns True if successful."""
    try:
        print(f"🔄 [{datetime.now().strftime('%H:%M:%S')}] Attempting: {repo_name}")
        
        result = subprocess.run([
            'python', 'scripts/collect_code_review_metrics.py',
            '--repo', repo_name,
            '--date', date
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0 and 'Rate limit' not in result.stdout:
            print(f"✅ SUCCESS: {repo_name}")
            return True
        else:
            if 'RATE_LIMITED' in result.stdout:
                print(f"⏳ Rate limited: {repo_name}")
            else:
                print(f"❌ Other error: {repo_name}")
                print(f"   Error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"⏱️ Timeout: {repo_name}")
        return False
    except Exception as e:
        print(f"❌ Exception for {repo_name}: {e}")
        return False

def main():
    repositories = [
        'razorpay/kube-manifests',
        'razorpay/vishnu'
    ]
    
    date = '2025-08-28'
    max_attempts = 12  # 2 hours worth of retries (every 10 min)
    retry_interval = 600  # 10 minutes
    
    print(f"🚀 Starting auto-retry for {len(repositories)} repositories")
    print(f"📅 Date: {date}")
    print(f"🔄 Max attempts: {max_attempts}")
    print(f"⏰ Retry interval: {retry_interval//60} minutes")
    print("=" * 60)
    
    remaining_repos = repositories.copy()
    
    for attempt in range(1, max_attempts + 1):
        if not remaining_repos:
            print("\n🎉 All repositories completed successfully!")
            break
            
        print(f"\n📊 ATTEMPT {attempt}/{max_attempts}")
        print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📂 Remaining repos: {len(remaining_repos)}")
        
        completed_this_round = []
        
        for repo in remaining_repos:
            if try_collect_repo(repo, date):
                completed_this_round.append(repo)
        
        # Remove completed repositories
        for repo in completed_this_round:
            remaining_repos.remove(repo)
        
        if remaining_repos and attempt < max_attempts:
            print(f"\n⏳ Waiting {retry_interval//60} minutes before next attempt...")
            print(f"   Still pending: {remaining_repos}")
            time.sleep(retry_interval)
    
    # Final status
    if remaining_repos:
        print(f"\n❌ INCOMPLETE: {len(remaining_repos)} repositories still failed:")
        for repo in remaining_repos:
            print(f"   • {repo}")
        sys.exit(1)
    else:
        print(f"\n✅ ALL COMPLETE: Successfully collected data for all repositories!")
        
        # Try to upload the newly collected data
        print(f"\n📤 Attempting to upload newly collected data...")
        try:
            upload_result = subprocess.run([
                'python', 'scripts/upload_metrics_to_api.py',
                '--date', date,
                '--api-url', 'http://localhost:28002',
                '--auth-token', 'admin:admin123',
                '--max-attempts', '3'
            ], timeout=300)
            
            if upload_result.returncode == 0:
                print("✅ Upload completed successfully!")
            else:
                print("❌ Upload failed - please run manually")
        except Exception as e:
            print(f"❌ Upload error: {e}")

if __name__ == "__main__":
    main()
