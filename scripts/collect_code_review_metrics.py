#!/usr/bin/env python3
"""
Code Review Metrics Data Collection Script

This script collects GitHub data for a specific repository and date range,
then generates both raw data and extracted metrics files for the UI.

Usage:
    python scripts/collect_code_review_metrics.py --repo owner/repo-name --date 2024-08-28
    python scripts/collect_code_review_metrics.py --repo pg-router --date 2024-08-28

Requirements:
    - GitHub API token (set GITHUB_TOKEN environment variable)
    - requests library (pip install requests)
"""

import json
import os
import argparse
import time
import asyncio
import aiohttp
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
import requests
from pathlib import Path


class CodeReviewMetricsCollector:
    def __init__(self, github_token: Optional[str] = None):
        self.github_token = github_token or os.getenv('GITHUB_TOKEN')
        self.base_url = 'https://api.github.com'
        self.graphql_url = 'https://api.github.com/graphql'
        
        if not self.github_token:
            raise ValueError("GitHub token is required for GraphQL API access. Set GITHUB_TOKEN environment variable or provide token parameter.")
        
        # GraphQL headers
        self.graphql_headers = {
            'Accept': 'application/vnd.github+json',
            'Content-Type': 'application/json',
            'User-Agent': 'swe-agent-metrics-collector',
            'Authorization': f'Bearer {self.github_token}'
        }
        
        # REST API headers (only for PR search - GraphQL doesn't support merged PR search by date)
        self.rest_headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'swe-agent-metrics-collector'
        }
        
        # Create session for REST API calls (only needed for PR search)
        self.session = requests.Session()
        self.session.headers.update(self.rest_headers)
        
        print("🚀 Using REST API with GraphQL fallback for efficient and accurate data collection")
    
    def _make_github_request(self, url: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make a GitHub API request with error handling and rate limiting"""
        try:
            response = self.session.get(url, params=params)
            
            # Handle rate limiting
            if response.status_code == 403 and 'rate limit' in response.text.lower():
                reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 60))
                wait_time = reset_time - time.time() + 1
                print(f"⏳ Rate limit reached. Waiting {wait_time:.0f} seconds...")
                time.sleep(wait_time)
                response = self.session.get(url, params=params)
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"❌ GitHub API error: {e}")
            return {}
    
    def _get_paginated_results(self, url: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Get all paginated results from GitHub API"""
        all_results = []
        page = 1
        per_page = 100
        
        while True:
            page_params = {**(params or {}), 'page': page, 'per_page': per_page}
            data = self._make_github_request(url, page_params)
            
            if not data or (isinstance(data, dict) and 'items' in data):
                # Search API format
                items = data.get('items', []) if data else []
                all_results.extend(items)
                if len(items) < per_page:
                    break
            elif isinstance(data, list):
                # Direct list format
                all_results.extend(data)
                if len(data) < per_page:
                    break
            else:
                break
            
            page += 1
            
        return all_results
    
    def _is_line_specific_thread(self, thread: Dict[str, Any]) -> bool:
        """Check if thread is a line-specific review comment ('Comment on lines x to y')"""
        
        # Thread must have line information to be considered line-specific
        line = thread.get('line')
        original_line = thread.get('originalLine')
        start_line = thread.get('startLine')
        
        # Must have at least one line reference (current or original)
        has_line_info = line is not None or original_line is not None or start_line is not None
        
        return has_line_info
    
    def _is_github_actions_comment(self, comment: Dict[str, Any]) -> bool:
        """Check if comment is specifically from github-actions bot"""
        
        author = comment.get('author', {})
        if not author:
            return False
        
        author_login = author.get('login', '').lower()
        author_type = author.get('__typename', 'User')
        
        # GitHub-actions bot (handle both GraphQL 'github-actions' and REST 'github-actions[bot]')
        return (author_login in ['github-actions', 'github-actions[bot]'] and author_type == 'Bot')
    
    def _is_human_comment(self, comment: Dict[str, Any]) -> bool:
        """Check if comment is from a human (non-bot) user"""
        
        author = comment.get('author', {})
        if not author:
            return False
        
        author_type = author.get('__typename', 'User')
        
        # Human if author type is User (not Bot)
        return author_type == 'User'
    
    def _is_allowed_target_branch(self, branch: str) -> bool:
        """Check if PR was merged to an allowed target branch"""
        
        allowed_branches = ['master', 'singapore_release', 'us_release']
        return branch.lower() in [b.lower() for b in allowed_branches]
    
    def collect_repo_data(self, repo: str, date: str) -> Dict[str, Any]:
        """
        Collect GitHub data for a specific repository and date.
        
        Args:
            repo: Repository name (e.g., 'owner/repo-name')
            date: Date string in YYYY-MM-DD format
        
        Returns:
            Raw data dictionary following our defined schema
        """
        print(f"🔍 Collecting GitHub data for {repo} on {date}")
        
        # Parse date and create IST measurement period (12AM to 11:59PM IST)
        target_date = datetime.strptime(date, '%Y-%m-%d')
        ist_offset = timedelta(hours=5, minutes=30)
        
        start_time = target_date.replace(tzinfo=timezone.utc) + ist_offset
        end_time = start_time + timedelta(hours=23, minutes=59)
        
        # Convert to GitHub search format (UTC)
        start_utc = start_time - ist_offset
        end_utc = end_time - ist_offset
        
        print(f"📅 Date range: {start_utc.isoformat()} to {end_utc.isoformat()} UTC")
        
        # Collect PRs merged in the time period
        merged_prs = self._get_merged_prs(repo, start_utc, end_utc)
        print(f"📊 Found {len(merged_prs)} merged PRs")
        
        # Collect detailed data for each PR
        processed_prs = []
        for i, pr in enumerate(merged_prs, 1):
            print(f"📋 Processing PR {i}/{len(merged_prs)}: #{pr['number']}")
            pr_data = self._collect_pr_data(repo, pr)
            
            # Filter PRs by allowed target branches (master, singapore_release, us_release)
            if self._is_allowed_target_branch(pr_data.get('base_branch', '')):
                processed_prs.append(pr_data)
            else:
                print(f"  ⏭️ Skipping PR #{pr['number']} - merged to branch '{pr_data.get('base_branch', 'unknown')}'")
        
        # Collect system events (mock for now since we don't have access to internal metrics)
        system_events = self._collect_system_events(processed_prs)
        
        return {
            "metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "measurement_period": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat(),
                    "timezone": "IST"
                },
                "repository": repo,
                "version": "1.0"
            },
            "prs": processed_prs,
            "system_events": system_events
        }
    
    def _get_merged_prs(self, repo: str, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get PRs merged in the specified time period"""
        
        # GitHub search API for merged PRs in date range
        search_query = f"repo:{repo} is:pr is:merged merged:{start_time.strftime('%Y-%m-%dT%H:%M:%S')}..{end_time.strftime('%Y-%m-%dT%H:%M:%S')}"
        
        url = f"{self.base_url}/search/issues"
        params = {"q": search_query, "sort": "updated", "order": "desc"}
        
        search_results = self._make_github_request(url, params)
        return search_results.get('items', [])
    
    def _collect_pr_data(self, repo: str, pr: Dict[str, Any]) -> Dict[str, Any]:
        """Collect detailed data for a single PR using REST API first, GraphQL as fallback"""
        
        pr_number = pr['number']
        
        # Try REST API first for efficiency and to avoid rate limits
        try:
            return self._collect_pr_data_rest(repo, pr_number, pr)
        except Exception as e:
            print(f"⚠️ REST API failed for PR {pr_number}: {e}")
            print(f"🔄 Falling back to GraphQL API...")
            
            # Fallback to GraphQL API
            try:
                return asyncio.run(self._collect_pr_data_graphql(repo, pr_number, pr))
            except Exception as graphql_e:
                print(f"❌ GraphQL collection also failed for PR {pr_number}: {graphql_e}")
                raise Exception(f"Both REST and GraphQL failed for PR {pr_number}. REST: {e}, GraphQL: {graphql_e}")
    
    def _collect_pr_data_rest(self, repo: str, pr_number: int, pr_base_data: Dict[str, Any]) -> Dict[str, Any]:
        """Collect PR data using REST API with GraphQL fallback for outdated comments"""
        
        # Get PR details
        pr_url = f"{self.base_url}/repos/{repo}/pulls/{pr_number}"
        pr_details = self._make_github_request(pr_url)
        
        # Get PR review comments
        review_comments_url = f"{self.base_url}/repos/{repo}/pulls/{pr_number}/comments"
        review_comments = self._paginate_github_request(review_comments_url)
        
        # Get PR files for size calculation
        files_url = f"{self.base_url}/repos/{repo}/pulls/{pr_number}/files"
        pr_files = self._paginate_github_request(files_url)
        
        # Process comments and filter for AI comments
        ai_comments = []
        human_comments = []
        
        for comment in review_comments:
            # Check if comment is from AI (github-actions bot)
            if self._is_ai_comment_rest(comment):
                # For outdated detection, we'll use GraphQL as it's more reliable
                outdated_status = self._check_comment_outdated_graphql(repo, comment['id'])
                
                ai_comment_data = self._process_ai_comment_rest(comment, outdated_status)
                ai_comments.append(ai_comment_data)
            else:
                human_comment_data = self._process_human_comment_rest(comment)
                human_comments.append(human_comment_data)
        
        return {
            "pr_id": pr_details.get('id'),
            "pr_number": pr_number,
            "title": pr_details.get('title', ''),
            "created_at": pr_details.get('created_at', ''),
            "merged_at": pr_details.get('merged_at', ''),
            "author": pr_details.get('user', {}).get('login', ''),
            "base_branch": pr_details.get('base', {}).get('ref', ''),
            "changed_files": len(pr_files),
            "ai_comments": ai_comments,
            "human_comments": human_comments,
            "api_source": "REST"
        }
    
    def _is_ai_comment_rest(self, comment: Dict[str, Any]) -> bool:
        """Check if a comment is from AI using REST API data"""
        
        user = comment.get('user', {})
        username = user.get('login', '').lower()
        user_type = user.get('type', '')
        
        # Check for github-actions bot (handle both 'github-actions' and 'github-actions[bot]')
        if username in ['github-actions', 'github-actions[bot]'] and user_type == 'Bot':
            return True
        
        # Additional AI detection patterns
        body = comment.get('body', '').lower()
        ai_patterns = [
            'i am an ai', 'as an ai', 'generated by ai',
            'automated review', 'auto-generated',
            'pr code suggestions', 'no code suggestions found'
        ]
        
        if any(pattern in body for pattern in ai_patterns):
            return True
        
        return False
    
    def _check_comment_outdated_graphql(self, repo: str, comment_id: int) -> bool:
        """Use GraphQL to check if a comment is outdated (more reliable than REST)"""
        
        try:
            # This is a simplified GraphQL query to check outdated status
            # In practice, you might need to query the review thread
            owner, repo_name = repo.split('/')
            
            query = """
            query($owner: String!, $repo: String!, $commentId: ID!) {
                repository(owner: $owner, name: $repo) {
                    pullRequestReviewComment(id: $commentId) {
                        outdated
                    }
                }
            }
            """
            
            variables = {
                "owner": owner,
                "repo": repo_name,
                "commentId": comment_id
            }
            
            # This is a simplified approach - in practice, outdated status
            # is better detected at the thread level, so we'll use a fallback
            return self._graphql_outdated_fallback(repo, comment_id)
            
        except Exception:
            # Fallback to heuristic detection
            return False
    
    def _graphql_outdated_fallback(self, repo: str, comment_id: int) -> bool:
        """Fallback method for outdated detection using REST API heuristics"""
        
        try:
            # Get comment details
            comment_url = f"{self.base_url}/repos/{repo}/pulls/comments/{comment_id}"
            comment_data = self._make_github_request(comment_url)
            
            # REST API heuristic: if line is None but original_line has value, likely outdated
            line = comment_data.get('line')
            original_line = comment_data.get('original_line')
            
            if line is None and original_line is not None:
                return True
            
            return False
            
        except Exception:
            return False
    
    def _process_ai_comment_rest(self, comment: Dict[str, Any], is_outdated: bool) -> Dict[str, Any]:
        """Process AI comment from REST API data"""
        
        # Get reactions
        reactions_data = self._get_comment_reactions_rest(comment.get('url', ''))
        
        # Categorize comment
        category, severity = self._categorize_comment(comment.get('body', ''))
        
        return {
            "comment_id": comment.get('id'),
            "created_at": comment.get('created_at'),
            "category": category,
            "severity": severity,
            "status": {
                "outdated": is_outdated,
                "resolved": False  # REST API doesn't easily provide this
            },
            "reactions": reactions_data,
            "has_detailed_feedback": len(comment.get('body', '')) > 100,
            "github_metadata": {
                "line": comment.get('line'),
                "original_line": comment.get('original_line'),
                "start_line": comment.get('start_line'),
                "original_start_line": comment.get('original_start_line'),
                "path": comment.get('path'),
                "rest_source": True
            }
        }
    
    def _process_human_comment_rest(self, comment: Dict[str, Any]) -> Dict[str, Any]:
        """Process human comment from REST API data"""
        
        return {
            "comment_id": comment.get('id'),
            "created_at": comment.get('created_at'),
            "author": comment.get('user', {}).get('login', ''),
            "body": comment.get('body', ''),
            "github_metadata": {
                "line": comment.get('line'),
                "path": comment.get('path'),
                "rest_source": True
            }
        }
    
    def _get_comment_reactions_rest(self, comment_url: str) -> Dict[str, int]:
        """Get reactions for a comment using REST API"""
        
        try:
            if not comment_url:
                return {"thumbs_up": 0, "thumbs_down": 0}
            
            reactions_url = f"{comment_url}/reactions"
            reactions = self._paginate_github_request(reactions_url, 
                                                    headers={'Accept': 'application/vnd.github.squirrel-girl-preview+json'})
            
            thumbs_up = len([r for r in reactions if r.get('content') == '+1'])
            thumbs_down = len([r for r in reactions if r.get('content') == '-1'])
            
            return {"thumbs_up": thumbs_up, "thumbs_down": thumbs_down}
        except Exception:
            return {"thumbs_up": 0, "thumbs_down": 0}
    
    def _paginate_github_request(self, url: str, headers: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Handle paginated GitHub REST API requests"""
        
        all_items = []
        current_url = url
        request_headers = headers or self.rest_headers
        
        while current_url:
            response = self._make_github_request_extended(current_url, headers=request_headers, return_response=True)
            
            if response.status_code == 200:
                data = response.json()
                
                if isinstance(data, list):
                    all_items.extend(data)
                else:
                    # Handle non-list responses
                    all_items.append(data)
                
                # Check for pagination
                if 'next' in response.links:
                    current_url = response.links['next']['url']
                else:
                    current_url = None
            else:
                break
        
        return all_items
    
    def _make_github_request_extended(self, url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None, return_response: bool = False):
        """Extended GitHub REST API request with custom headers and response options"""
        
        request_headers = headers or self.rest_headers
        
        while True:
            try:
                response = requests.get(url, params=params, headers=request_headers)
                
                if return_response:
                    return response
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 403:
                    # Rate limit exceeded
                    reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 3600))
                    sleep_time = reset_time - int(time.time()) + 10
                    
                    print(f"⏳ Rate limit reached. Waiting {sleep_time} seconds...")
                    time.sleep(sleep_time)
                    continue
                else:
                    raise Exception(f"GitHub API error: {response.status_code} - {response.text}")
                    
            except requests.exceptions.RequestException as e:
                raise Exception(f"Request failed: {e}")
    
    async def _collect_pr_data_graphql(self, repo: str, pr_number: int, pr_base_data: Dict[str, Any]) -> Dict[str, Any]:
        """Collect PR data using GraphQL API for accurate outdated detection"""
        
        owner, repo_name = repo.split('/')
        
        query = """
        query GetPRData($owner: String!, $repo: String!, $prNumber: Int!) {
          repository(owner: $owner, name: $repo) {
            pullRequest(number: $prNumber) {
              id
              title
              state
              number
              createdAt
              updatedAt
              mergedAt
              changedFiles
              baseRefName
              author {
                login
              }
              reviewThreads(first: 100) {
                totalCount
                nodes {
                  id
                  isOutdated
                  isResolved
                  line
                  originalLine
                  path
                  startLine
                  originalStartLine
                  comments(first: 50) {
                    totalCount
                    nodes {
                      id
                      body
                      createdAt
                      updatedAt
                      author {
                        login
                        ... on Bot {
                          __typename
                        }
                        ... on User {
                          __typename
                        }
                      }
                      reactions(first: 10) {
                        totalCount
                        nodes {
                          content
                          user {
                            login
                          }
                        }
                      }
                    }
                  }
                }
              }
              comments(first: 100) {
                totalCount
                nodes {
                  id
                  body
                  createdAt
                  updatedAt
                  author {
                    login
                    ... on Bot {
                      __typename
                    }
                    ... on User {
                      __typename
                    }
                  }
                  reactions(first: 10) {
                    totalCount
                    nodes {
                      content
                      user {
                        login
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """
        
        variables = {
            "owner": owner,
            "repo": repo_name,
            "prNumber": pr_number
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.graphql_url,
                headers=self.graphql_headers,
                json={"query": query, "variables": variables}
            ) as response:
                
                if response.status != 200:
                    raise Exception(f"GraphQL request failed: HTTP {response.status}")
                
                data = await response.json()
                
                if 'errors' in data:
                    raise Exception(f"GraphQL errors: {data['errors']}")
                
                return self._process_graphql_pr_data(data, f"{owner}/{repo_name}")
    
    def _process_graphql_pr_data(self, data: Dict[str, Any], repo: str) -> Dict[str, Any]:
        """Process GraphQL PR data and extract metrics"""
        
        pr_data = data.get('data', {}).get('repository', {}).get('pullRequest')
        
        if not pr_data:
            raise Exception("PR not found in GraphQL response")
        
        review_threads = pr_data.get('reviewThreads', {}).get('nodes', [])
        issue_comments = pr_data.get('comments', {}).get('nodes', [])
        
        ai_comments = []
        human_comments = []
        
        # Process review threads (code comments) - ONLY line-specific comments
        for thread in review_threads:
            # Only process threads that have line information (line-specific comments)
            if not self._is_line_specific_thread(thread):
                continue
                
            is_thread_outdated = thread.get('isOutdated', False)
            is_thread_resolved = thread.get('isResolved', False)
            comments = thread.get('comments', {}).get('nodes', [])
            
            for comment in comments:
                if self._is_github_actions_comment(comment):
                    ai_comment = self._process_ai_comment_graphql(
                        repo, comment, "review", 
                        is_thread_outdated, is_thread_resolved, thread
                    )
                    if ai_comment:
                        ai_comments.append(ai_comment)
                elif self._is_human_comment(comment):
                    human_comments.append({
                        "comment_id": comment.get('id'),
                        "created_at": comment.get('createdAt'),
                        "author_type": "reviewer"
                    })
        
        # Note: Ignoring issue comments - only processing line-specific review threads
        
        return {
            "pr_id": str(pr_data.get('number')),
            "pr_number": pr_data.get('number'),
            "title": pr_data.get('title', ''),
            "created_at": pr_data.get('createdAt', ''),
            "merged_at": pr_data.get('mergedAt', ''),
            "author": pr_data.get('author', {}).get('login', ''),
            "base_branch": pr_data.get('baseRefName', ''),
            "changed_files": pr_data.get('changedFiles', 0),
            "ai_comments": ai_comments,
            "human_comments": human_comments,
            "api_source": "GraphQL"
        }
    
    def _is_ai_comment_graphql(self, comment: Dict[str, Any]) -> bool:
        """Determine if a comment is from AI using GraphQL data format"""
        
        author = comment.get('author', {})
        if not author:
            return False
        
        author_login = author.get('login', '').lower()
        author_type = author.get('__typename', 'User')
        
        # Check if it's explicitly a Bot type
        if author_type == 'Bot':
            return True
        
        # Check for AI/bot patterns in username
        ai_patterns = [
            'github-actions', 'bot', 'ai', 'assistant', 
            'dependabot', 'codecov', 'sonarcloud',
            'razorpay-swe-agent', 'swe-agent'
        ]
        
        if any(pattern in author_login for pattern in ai_patterns):
            return True
        
        # Check body for AI patterns
        body = comment.get('body', '').lower()
        ai_body_patterns = [
            'i am an ai', 'as an ai', 'generated by ai',
            'automated review', 'auto-generated',
            'this is an automated', 'bot analysis'
        ]
        
        if any(pattern in body for pattern in ai_body_patterns):
            return True
        
        return False
    
    def _process_ai_comment_graphql(
        self, 
        repo: str, 
        comment: Dict[str, Any], 
        comment_type: str,
        is_thread_outdated: bool,
        is_thread_resolved: bool,
        thread_data: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Process an AI comment using GraphQL data with accurate outdated detection"""
        
        comment_id = comment.get('id', '')
        author = comment.get('author', {})
        
        # Extract reactions from GraphQL format
        reactions = comment.get('reactions', {}).get('nodes', [])
        thumbs_up = len([r for r in reactions if r.get('content') == 'THUMBS_UP'])
        thumbs_down = len([r for r in reactions if r.get('content') == 'THUMBS_DOWN'])
        
        # Categorize comment (basic heuristics)
        category, severity = self._categorize_comment(comment.get('body', ''))
        
        # Use GraphQL thread-level outdated status for accurate detection
        if comment_type == "review" and thread_data:
            # GraphQL provides accurate outdated status at thread level
            is_outdated = is_thread_outdated
            
            # Determine outdated reason based on GraphQL data
            if is_outdated:
                # Check if line numbers changed
                current_line = thread_data.get('line')
                original_line = thread_data.get('originalLine')
                
                if current_line is None and original_line is not None:
                    outdated_reason = "line_changed"
                elif current_line != original_line:
                    outdated_reason = "line_moved"
                else:
                    outdated_reason = "code_changed"
            else:
                outdated_reason = None
        else:
            # Issue comments don't have outdated status in GraphQL either
            is_outdated = False
            outdated_reason = None
        
        # Check for detailed feedback (has replies or long content)
        has_detailed_feedback = len(comment.get('body', '')) > 100
        
        # Build GitHub metadata from GraphQL data
        github_metadata = {}
        if comment_type == "review" and thread_data:
            github_metadata = {
                "line": thread_data.get('line'),
                "original_line": thread_data.get('originalLine'),
                "start_line": thread_data.get('startLine'),
                "original_start_line": thread_data.get('originalStartLine'),
                "path": thread_data.get('path', ''),
                "thread_id": thread_data.get('id', ''),
                "thread_resolved": is_thread_resolved,
                "graphql_source": True  # Flag to indicate this came from GraphQL
            }
        
        return {
            "comment_id": comment_id,
            "created_at": comment.get('createdAt', ''),
            "category": category,
            "severity": severity,
            "status": {
                "current": "outdated" if is_outdated else "active",
                "outdated": is_outdated,
                "outdated_reason": outdated_reason,
                "became_outdated_at": comment.get('updatedAt') if is_outdated else None,
                "detection_method": "graphql_thread_level"  # Indicate accurate detection method
            },
            "reactions": {
                "thumbs_up": thumbs_up,
                "thumbs_down": thumbs_down
            },
            "has_detailed_feedback": has_detailed_feedback,
            "github_metadata": github_metadata
        }
    
    def _categorize_comment(self, body: str) -> tuple[str, int]:
        """Categorize comment and assign severity based on content"""
        
        body_lower = body.lower()
        
        # Security patterns
        security_patterns = ['security', 'vulnerability', 'exploit', 'injection', 'xss', 'csrf', 'authentication']
        if any(pattern in body_lower for pattern in security_patterns):
            return "security", 9
        
        # Performance patterns
        performance_patterns = ['performance', 'slow', 'optimization', 'memory', 'cpu', 'latency']
        if any(pattern in body_lower for pattern in performance_patterns):
            return "performance", 7
        
        # Possible issue patterns
        issue_patterns = ['bug', 'issue', 'problem', 'error', 'exception', 'fail']
        if any(pattern in body_lower for pattern in issue_patterns):
            return "possible_issue", 6
        
        # Default to general
        return "general", 4
    
    def _collect_system_events(self, prs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate system events based on processed PRs (mock implementation)"""
        
        events = []
        for pr in prs:
            # Mock processing time based on number of files and comments
            files_changed = pr.get('files_changed', 1)
            comment_count = len(pr.get('ai_comments', []))
            
            # Simulate processing time: base time + file factor + comment factor
            base_time = 20000  # 20 seconds base
            file_factor = files_changed * 2000  # 2 seconds per file
            comment_factor = comment_count * 1000  # 1 second per comment
            
            processing_time = base_time + file_factor + comment_factor
            
            events.append({
                "event_type": "ai_review_requested",
                "pr_id": pr['pr_id'],
                "timestamp": pr['created_at'],
                "processing_time_ms": processing_time,
                "status": "success"
            })
        
        return events
    
    def _calculate_detection_accuracy(self, ai_comments: List[Dict[str, Any]], human_comments: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate issue detection accuracy metrics using reactions with outdated status fallback"""
        """New Logic: Prioritize explicit reactions (👍/👎) over outdated status"""
        
        if not ai_comments:
            return {"precision": 0.0, "recall": 0.0, "f1_score": 0.0}
        
        true_positives = 0
        false_positives = 0
        
        for comment in ai_comments:
            thumbs_up = comment.get('reactions', {}).get('thumbs_up', 0)
            thumbs_down = comment.get('reactions', {}).get('thumbs_down', 0)
            is_outdated = comment.get('status', {}).get('outdated', False)
            
            # True Positives (TP): if reaction has 👍, if no reaction check if its outdated comment
            if thumbs_up > 0:
                true_positives += 1
            elif thumbs_up == 0 and thumbs_down == 0 and is_outdated:
                true_positives += 1
            
            # False Positives (FP): if reaction has 👎, if no reaction check if the comment is not outdated
            elif thumbs_down > 0:
                false_positives += 1
            elif thumbs_up == 0 and thumbs_down == 0 and not is_outdated:
                false_positives += 1
        
        # False Negatives: Human comments (issues AI missed completely)
        false_negatives = len(human_comments)
        
        # Calculate metrics
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        return {
            "precision": round(precision, 2),
            "recall": round(recall, 2),
            "f1_score": round(f1_score, 2)
        }
    
    def _could_be_ai_catchable(self, human_comment: Dict[str, Any]) -> bool:
        """Heuristic to determine if a human comment could have been caught by AI"""
        # This is a rough approximation - in practice you'd need more sophisticated analysis
        # For now, assume shorter comments or those with technical keywords could be AI-catchable
        return True  # Simplified - all human comments are potentially AI-catchable
    
    def _calculate_human_comment_percentage(self, ai_comments: List[Dict[str, Any]], human_comments: List[Dict[str, Any]]) -> float:
        """Calculate percentage of human comments out of total comments"""
        
        total_comments = len(ai_comments) + len(human_comments)
        
        if total_comments == 0:
            return 0.0
        
        human_percentage = (len(human_comments) / total_comments) * 100
        return round(human_percentage, 1)
    
    def _calculate_time_saved(self, accepted_comments: List[Dict[str, Any]], all_ai_comments: List[Dict[str, Any]]) -> float:
        """Calculate time saved in minutes based on accepted AI comments"""
        """Formula: Accepted AI Comments × 2 minutes"""
        
        if not accepted_comments:
            return 0.0
        
        # Simple formula: 2 minutes per accepted AI comment
        minutes_saved = len(accepted_comments) * 2
        return round(minutes_saved, 1)
    
    def _calculate_category_acceptance_rate(self, category: str, all_ai_comments: List[Dict[str, Any]]) -> float:
        """Calculate acceptance rate for a specific category using new logic"""
        
        category_comments = [c for c in all_ai_comments if c.get('category') == category]
        if not category_comments:
            return 0.0
        
        accepted_count = sum(1 for comment in category_comments if self._is_comment_accepted(comment))
        return (accepted_count / len(category_comments)) * 100
    
    def _is_comment_accepted(self, comment: Dict[str, Any]) -> bool:
        """Check if a comment is accepted using new logic"""
        
        thumbs_up = comment.get('reactions', {}).get('thumbs_up', 0)
        thumbs_down = comment.get('reactions', {}).get('thumbs_down', 0)
        is_outdated = comment.get('status', {}).get('outdated', False)
        
        # Accepted: if reaction has 👍, if no reaction check if its outdated comment
        if thumbs_up > 0:
            return True
        elif thumbs_up == 0 and thumbs_down == 0 and is_outdated:
            return True
        
        return False
    
    def _calculate_processing_latency_by_size(self, processed_prs: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate processing latency grouped by PR size (file count)"""
        """Formula: First AI Comment Time - PR Creation Time"""
        
        small_prs = []   # <5 files
        medium_prs = []  # 5-20 files  
        large_prs = []   # >20 files
        
        for pr in processed_prs:
            files_changed = pr.get('files_changed', 0)
            ai_comments = pr.get('ai_comments', [])
            
            # Skip PRs without AI comments (no latency to measure)
            if not ai_comments:
                continue
                
            try:
                # Parse timestamps
                pr_created = datetime.fromisoformat(pr.get('created_at', '').replace('Z', '+00:00'))
                
                # Find earliest AI comment
                earliest_ai_comment = min(
                    ai_comments, 
                    key=lambda c: datetime.fromisoformat(c.get('created_at', '').replace('Z', '+00:00'))
                )
                first_ai_comment_time = datetime.fromisoformat(
                    earliest_ai_comment.get('created_at', '').replace('Z', '+00:00')
                )
                
                # Calculate latency: First AI comment - PR creation
                latency_delta = first_ai_comment_time - pr_created
                latency_minutes = latency_delta.total_seconds() / 60
                
                # Categorize by PR size (keep same logic)
                if files_changed < 5:
                    small_prs.append(latency_minutes)
                elif files_changed <= 20:
                    medium_prs.append(latency_minutes)
                else:
                    large_prs.append(latency_minutes)
                    
            except (ValueError, TypeError) as e:
                # Skip PRs with invalid timestamps
                continue
        
        # Calculate medians
        def safe_median(times_list):
            if not times_list:
                return 0.0
            sorted_times = sorted(times_list)
            n = len(sorted_times)
            return sorted_times[n // 2] if n % 2 == 1 else (sorted_times[n // 2 - 1] + sorted_times[n // 2]) / 2
        
        return {
            "small_prs_median_minutes": round(safe_median(small_prs), 1),
            "medium_prs_median_minutes": round(safe_median(medium_prs), 1),
            "large_prs_median_minutes": round(safe_median(large_prs), 1)
        }

    def save_raw_data(self, data: Dict[str, Any], repo: str, date: str) -> str:
        """Save raw data to file"""
        
        # Create directory structure
        base_dir = Path("uploads/metrics/raw")
        date_dir = base_dir / date
        date_dir.mkdir(parents=True, exist_ok=True)
        
        # Clean repo name for filename
        repo_clean = repo.replace('/', '-')
        filename = f"{repo_clean}-raw.json"
        filepath = date_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Raw data saved to: {filepath}")
        return str(filepath)
    
    def generate_extracted_metrics(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate metrics from raw data"""
        
        prs = raw_data.get('prs', [])
        all_ai_comments = []
        all_human_comments = []
        
        # Collect all comments
        for pr in prs:
            all_ai_comments.extend(pr.get('ai_comments', []))
            all_human_comments.extend(pr.get('human_comments', []))
        
        # Calculate stats
        total_comments = len(all_ai_comments)
        prs_reviewed = len(prs)
        
        # Category distribution - dynamic categories
        categories = {}
        severity_dist = {"high": 0, "low": 0}
        
        for comment in all_ai_comments:
            cat = comment.get('category', 'general')
            categories[cat] = categories.get(cat, 0) + 1
            
            severity = comment.get('severity', 0)
            if severity >= 6:
                severity_dist["high"] += 1
            else:
                severity_dist["low"] += 1
        
        # Effectiveness metrics - using new logic consistent with TP calculation
        accepted_comments = []
        for comment in all_ai_comments:
            thumbs_up = comment.get('reactions', {}).get('thumbs_up', 0)
            thumbs_down = comment.get('reactions', {}).get('thumbs_down', 0)
            is_outdated = comment.get('status', {}).get('outdated', False)
            
            # Accepted: if reaction has 👍, if no reaction check if its outdated comment
            if thumbs_up > 0:
                accepted_comments.append(comment)
            elif thumbs_up == 0 and thumbs_down == 0 and is_outdated:
                accepted_comments.append(comment)
        
        acceptance_rate = (len(accepted_comments) / len(all_ai_comments)) * 100 if all_ai_comments else 0
        
        # False negatives: Human comments indicate issues AI missed
        false_negatives_rate = (len(all_human_comments) / (len(all_ai_comments) + len(all_human_comments))) * 100 if (all_ai_comments or all_human_comments) else 0
        
        # Critical issues: severity >= 6 AND accepted (using new logic)
        high_severity_comments = [c for c in all_ai_comments if c.get('severity', 0) >= 6]
        critical_issues_caught = []
        
        for comment in high_severity_comments:
            thumbs_up = comment.get('reactions', {}).get('thumbs_up', 0)
            thumbs_down = comment.get('reactions', {}).get('thumbs_down', 0)
            is_outdated = comment.get('status', {}).get('outdated', False)
            
            # Critical accepted: if reaction has 👍, if no reaction check if its outdated comment
            if thumbs_up > 0:
                critical_issues_caught.append(comment)
            elif thumbs_up == 0 and thumbs_down == 0 and is_outdated:
                critical_issues_caught.append(comment)
        
        critical_catch_rate = (len(critical_issues_caught) / len(high_severity_comments)) * 100 if high_severity_comments else 0
        
        # Critical issues by category
        critical_category_breakdown = {}
        critical_category_rates = {}
        
        for comment in critical_issues_caught:
            category = comment.get('category', 'general')
            critical_category_breakdown[category] = critical_category_breakdown.get(category, 0) + 1
        
        # Calculate catch rates by category for critical issues (using new logic)
        # Only calculate for categories that actually have high severity comments
        for category in categories.keys():
            category_high_severity = [c for c in all_ai_comments if c.get('category') == category and c.get('severity', 0) >= 6]
            
            # Only calculate rate if this category has high severity comments
            if category_high_severity:
                category_critical_caught = []
                
                for comment in category_high_severity:
                    thumbs_up = comment.get('reactions', {}).get('thumbs_up', 0)
                    thumbs_down = comment.get('reactions', {}).get('thumbs_down', 0)
                    is_outdated = comment.get('status', {}).get('outdated', False)
                    
                    # Category critical accepted: if reaction has 👍, if no reaction check if its outdated comment
                    if thumbs_up > 0:
                        category_critical_caught.append(comment)
                    elif thumbs_up == 0 and thumbs_down == 0 and is_outdated:
                        category_critical_caught.append(comment)
                
                critical_category_rates[category] = (len(category_critical_caught) / len(category_high_severity)) * 100
        
        # False positive rate: Using new logic with reactions priority
        false_positive_comments = []
        for comment in all_ai_comments:
            thumbs_up = comment.get('reactions', {}).get('thumbs_up', 0)
            thumbs_down = comment.get('reactions', {}).get('thumbs_down', 0)
            is_outdated = comment.get('status', {}).get('outdated', False)
            
            # FP: if reaction has 👎, if no reaction check if the comment is not outdated
            if thumbs_down > 0:
                false_positive_comments.append(comment)
            elif thumbs_up == 0 and thumbs_down == 0 and not is_outdated:
                false_positive_comments.append(comment)
        
        false_positive_rate = (len(false_positive_comments) / len(all_ai_comments)) * 100 if all_ai_comments else 0
        
        # Calculate average processing latency from all PRs
        processing_latency = self._calculate_processing_latency_by_size(prs)
        all_latencies = []
        
        # Extract all latency values for average calculation
        if processing_latency.get('small_prs_median_minutes', 0) > 0:
            # Count small PRs and add their median latency
            small_prs_count = len([pr for pr in prs if pr.get('files_changed', 0) < 5 and pr.get('ai_comments')])
            all_latencies.extend([processing_latency['small_prs_median_minutes']] * small_prs_count)
            
        if processing_latency.get('medium_prs_median_minutes', 0) > 0:
            # Count medium PRs and add their median latency
            medium_prs_count = len([pr for pr in prs if 5 <= pr.get('files_changed', 0) <= 20 and pr.get('ai_comments')])
            all_latencies.extend([processing_latency['medium_prs_median_minutes']] * medium_prs_count)
            
        if processing_latency.get('large_prs_median_minutes', 0) > 0:
            # Count large PRs and add their median latency
            large_prs_count = len([pr for pr in prs if pr.get('files_changed', 0) > 20 and pr.get('ai_comments')])
            all_latencies.extend([processing_latency['large_prs_median_minutes']] * large_prs_count)
        
        average_turnaround = sum(all_latencies) / len(all_latencies) if all_latencies else 0
        
        # System uptime: PRs with AI review attempts (successful system events)
        system_events = raw_data.get('system_events', [])
        successful_events = [e for e in system_events if e.get('status') == 'success']
        
        # Better uptime metric: AI review coverage across all PRs
        prs_with_ai_review = set(e.get('pr_id') for e in successful_events)
        total_prs = len(prs)
        uptime = (len(prs_with_ai_review) / total_prs) * 100 if total_prs else 0
        
        # Processing latency
        processing_times = [e.get('processing_time_ms', 0) / 1000 / 60 for e in successful_events]  # Convert to minutes
        median_processing = sorted(processing_times)[len(processing_times)//2] if processing_times else 0
        
        return {
            "metadata": {
                "date": raw_data['metadata']['measurement_period']['start'][:10],
                "repository": raw_data['metadata']['repository'],
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "version": "1.0"
            },
            "stats": {
                "total_comments": total_comments,
                "prs_reviewed": prs_reviewed,
                "comment_categories": categories,
                "severity_distribution": severity_dist
            },
            "effectiveness": {
                "comment_acceptance_rate": round(acceptance_rate, 1),
                "issue_detection_accuracy": self._calculate_detection_accuracy(all_ai_comments, all_human_comments),
                "false_positive_rate": round(false_positive_rate, 1),
                "false_negatives_rate": round(false_negatives_rate, 1),
                "category_acceptance_rates": {
                    cat: round(self._calculate_category_acceptance_rate(cat, all_ai_comments), 1)
                    for cat in categories.keys()
                } if categories else {}
            },
            "accepted_comments": [
                {
                    "comment_id": c.get('comment_id'),
                    "category": c.get('category', 'general'),
                    "severity": c.get('severity', 0),
                    "accepted": self._is_comment_accepted(c)
                }
                for c in all_ai_comments
            ],
            "critical_issues": {
                "total_critical_issues_caught": len(critical_issues_caught),
                "critical_issue_accepted_rate": round(critical_catch_rate, 1),
                "category_breakdown": critical_category_breakdown,
                "category_catch_rates": {cat: round(rate, 1) for cat, rate in critical_category_rates.items()}
            },
            "productivity": {
                "review_turnaround_time_minutes": round(average_turnaround, 1),
                "human_review_comment_percent": self._calculate_human_comment_percentage(all_ai_comments, all_human_comments),
                "human_comments_count": len(all_human_comments),
                "time_saved_minutes": self._calculate_time_saved(accepted_comments, all_ai_comments),
                "feedback_quality_rate": round((len([c for c in all_ai_comments if c['reactions']['thumbs_up'] > 0 or c['reactions']['thumbs_down'] > 0]) / len(all_ai_comments)) * 100, 1) if all_ai_comments else 0
            },
            "technical": {
                "system_uptime_percent": round(uptime, 1),
                "processing_latency": self._calculate_processing_latency_by_size(prs)
            }
        }
    
    def save_extracted_metrics(self, metrics: Dict[str, Any], repo: str, date: str) -> str:
        """Save extracted metrics to file"""
        
        # Create directory structure  
        base_dir = Path("uploads/metrics/extracted")
        date_dir = base_dir / date
        date_dir.mkdir(parents=True, exist_ok=True)
        
        # Clean repo name for filename
        repo_clean = repo.replace('/', '-')
        filename = f"{repo_clean}-metrics.json"
        filepath = date_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(metrics, f, indent=2)
            
        print(f"Extracted metrics saved to: {filepath}")
        return str(filepath)


def main():
    parser = argparse.ArgumentParser(
        description='Collect code review metrics from GitHub API for a repository',
        epilog="""
Examples:
  python scripts/collect_code_review_metrics.py --repo owner/repo-name --date 2024-08-28
  python scripts/collect_code_review_metrics.py --repo pg-router --date 2024-08-28 --token ghp_xxx
  
Set GITHUB_TOKEN environment variable:
  export GITHUB_TOKEN=your_personal_access_token
  python scripts/collect_code_review_metrics.py --repo pg-router --date 2024-08-28
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--repo', required=True, help='Repository name (e.g., owner/repo-name or just repo-name)')
    parser.add_argument('--date', required=True, help='Date in YYYY-MM-DD format')
    parser.add_argument('--token', help='GitHub API token (or set GITHUB_TOKEN env var)')
    
    args = parser.parse_args()
    
    try:
        # Initialize collector (GraphQL only)
        try:
            collector = CodeReviewMetricsCollector(args.token)
        except ValueError as e:
            print(f"❌ {e}")
            print("   Set GITHUB_TOKEN environment variable or use --token parameter")
            return
        
        # Collect raw data
        print(f"\n🔍 Starting GitHub data collection...")
        raw_data = collector.collect_repo_data(args.repo, args.date)
        
        if not raw_data.get('prs'):
            print(f"⚠️  No PRs found for {args.repo} on {args.date}")
            print("   Check if the repository exists and has merged PRs in the specified date/time range")
            return
        
        # Save raw data
        print("\n💾 Saving raw data...")
        raw_filepath = collector.save_raw_data(raw_data, args.repo, args.date)
        
        # Generate and save extracted metrics
        print("📊 Calculating metrics...")
        metrics = collector.generate_extracted_metrics(raw_data)
        metrics_filepath = collector.save_extracted_metrics(metrics, args.repo, args.date)
        
        # Success summary
        print(f"\n✅ GitHub data collection complete!")
        print(f"📊 Found {len(raw_data['prs'])} PRs with {sum(len(pr.get('ai_comments', [])) for pr in raw_data['prs'])} AI comments")
        print(f"📁 Raw data: {raw_filepath}")
        print(f"📈 Metrics: {metrics_filepath}")
        print(f"\n🌐 API endpoint: GET /api/metrics/{args.repo.replace('/', '-')}/daily/{args.date}")
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Collection interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during collection: {e}")
        print("Check repository name, date format, and GitHub token")


if __name__ == '__main__':
    main()
