"""
I18N Sub-Agent Implementation

Handles extraction, filtering, and analysis of internationalization (i18n) comments.
"""

import os
import re
import logging
import requests
from typing import List, Dict, Any, Optional, Tuple

from src.services.comment_analyzer.sub_agent_base import (
    SubAgentBase,
    Comment,
    AnalysisResult,
    SeverityLevel
)
from src.services.comment_analyzer.review_identifiers import (
    ReviewType,
    identify_review_type,
    AI_CODE_REVIEW_HEADER
)
from src.services.comment_analyzer.agents.config_loader import SubAgentConfigLoader

logger = logging.getLogger(__name__)


class FileFilter:
    """Handles file filtering by extensions and glob patterns"""

    def __init__(self,
                 include_extensions: List[str] = None,
                 exclude_extensions: List[str] = None,
                 exclude_patterns: List[str] = None):
        self.include_extensions = [ext.lower() if ext.startswith('.') else f'.{ext.lower()}'
                                   for ext in (include_extensions or [])]
        self.exclude_extensions = [ext.lower() if ext.startswith('.') else f'.{ext.lower()}'
                                   for ext in (exclude_extensions or [])]
        self.exclude_patterns = exclude_patterns or []

    def should_exclude(self, file_path: Optional[str]) -> bool:
        if not file_path:
            return False

        import os
        from pathlib import PurePath

        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        # Check include extensions (whitelist)
        if self.include_extensions:
            if ext not in self.include_extensions:
                logger.info(f"[FileFilter] Excluding '{file_path}' (extension '{ext}' not in include list)")
                return True

        # Check exclude extensions (blacklist)
        if self.exclude_extensions:
            if ext in self.exclude_extensions:
                logger.info(f"[FileFilter] Excluding '{file_path}' (extension '{ext}' in exclude list)")
                return True

        # Check exclude patterns (glob patterns)
        if self.exclude_patterns:
            normalized_path = file_path.replace("\\", "/")
            path = PurePath(normalized_path)

            for pattern in self.exclude_patterns:
                if path.match(pattern):
                    logger.info(f"[FileFilter] Excluding '{file_path}' (matched pattern: {pattern})")
                    return True

        return False

    def filter_comments(self, comments: List[Comment]) -> List[Comment]:
        filtered = []
        excluded_count = 0

        for comment in comments:
            if self.should_exclude(comment.file_path):
                comment.excluded = True
                excluded_count += 1
            filtered.append(comment)

        if excluded_count > 0:
            logger.info(f"[FileFilter] Excluded {excluded_count} comments from {len(comments)} total")

        return filtered


class I18nSubAgent(SubAgentBase):
    """I18N sub-agent for analyzing internationalization comments"""

    def __init__(self, config: Dict[str, Any], github_token: str, repository: str, pr_number: int):
        # Load default config from JSON and merge with passed config
        default_config = SubAgentConfigLoader.load_config("i18n")
        merged_config = SubAgentConfigLoader.merge_config(default_config, config)
        super().__init__(merged_config, github_token, repository, pr_number)

        # Initialize file filter with extensions and patterns
        filter_config = merged_config.get("filter", {})
        self.file_filter = FileFilter(
            include_extensions=filter_config.get("include_extensions", []),
            exclude_extensions=filter_config.get("exclude_extensions", []),
            exclude_patterns=filter_config.get("exclude_patterns", [])
        )

        self.headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
        }
        self.base_url = f"https://api.github.com/repos/{repository}"

        # Authorized team for TP/FP feedback
        auth_config = merged_config.get("authorization", {})
        self.authorization_enabled = auth_config.get("enabled", False)
        self.authorized_team = auth_config.get("authorized_team")
        self._authorized_members = None  # Cached team members

        if self.authorization_enabled and self.authorized_team:
            logger.info(f"[{self.name}] Authorization feedback enabled")
            logger.info(f"[{self.name}] Authorized team: {self.authorized_team}")
        else:
            logger.info(f"[{self.name}] Authorization feedback disabled")

    def execute(self, all_reviews: List[Dict[str, Any]]) -> 'SubAgentResult':
        """
        Execute I18N comment analysis workflow.

        Custom workflow:
        1. Extract comments from AI Code Review
        2. Filter by [I18N, importance: X] tag
        3. Apply file filters and score severity
        4. Check for authorized feedback (TP/FP from atlas-admins)
        5. Auto-resolve FP comments, analyze remaining with Claude
        6. Determine actions and return results
        """
        from src.services.comment_analyzer.sub_agent_base import SubAgentResult

        logger.info(f"\n[{self.name}] Starting I18N analysis workflow")

        # Step 1: Extract comments from AI Code Review
        logger.info(f"\n[{self.name}] Step 1: Extracting comments from AI Code Review")
        raw_comments = self._extract_from_ai_review(all_reviews)

        if not raw_comments:
            logger.info(f"[{self.name}] No AI Code Review comments found")
            return self._create_empty_result()

        # Step 2: Filter by I18N tag
        logger.info(f"\n[{self.name}] Step 2: Filtering by [I18N, importance: X] tag")
        tagged_comments = self._filter_by_i18n_tag(raw_comments)

        if not tagged_comments:
            logger.info(f"[{self.name}] No I18N tagged comments found")
            return self._create_empty_result()

        # Step 3: Apply file filters and score
        logger.info(f"\n[{self.name}] Step 3: Filtering and scoring {len(tagged_comments)} comments")
        scored_comments = self._apply_filters_and_score(tagged_comments)

        # Step 4: Check authorized feedback and split FP/TP
        logger.info(f"\n[{self.name}] Step 4: Checking authorized feedback")
        fp_comments, comments_to_analyze = self._check_feedback_and_split(scored_comments)

        # Step 5: Analyze remaining comments with Claude
        logger.info(f"\n[{self.name}] Step 5: Analyzing {len(comments_to_analyze)} comments with Claude")
        analysis_results = self._analyze_with_claude(comments_to_analyze)

        # Step 6: Add FP auto-resolved to results
        logger.info(f"\n[{self.name}] Step 6: Adding {len(fp_comments)} FP auto-resolved comments")
        combined_results = self._combine_results(analysis_results, fp_comments)

        # Step 7: Determine actions
        logger.info(f"\n[{self.name}] Step 7: Determining actions")
        result = self.determine_actions(combined_results)

        logger.info(f"\n[{self.name}] Workflow complete: Status = {result.status}")
        return result

    def _get_authorized_members(self) -> List[str]:
        """Fetch authorized team members who can mark TP/FP"""
        # If authorization is disabled, return empty list
        if not self.authorization_enabled or not self.authorized_team:
            self._authorized_members = []
            return []

        if self._authorized_members is not None:
            return self._authorized_members

        try:
            # Parse team slug from format "org/team-slug"
            if "/" not in self.authorized_team:
                logger.warning(f"Invalid team format: {self.authorized_team}, expected 'org/team-slug'")
                self._authorized_members = []
                return []

            org, team_slug = self.authorized_team.split("/", 1)
            url = f"https://api.github.com/orgs/{org}/teams/{team_slug}/members"

            logger.info(f"Fetching authorized team members from: {self.authorized_team}")

            members = []
            page = 1

            while True:
                response = requests.get(
                    url,
                    headers=self.headers,
                    params={"page": page, "per_page": 100}
                )

                if response.status_code != 200:
                    logger.warning(f"Could not fetch team members (status {response.status_code}): {response.text[:200]}")
                    break

                page_members = response.json()
                if not page_members:
                    break

                members.extend([m.get("login") for m in page_members if m.get("login")])
                page += 1

            self._authorized_members = members
            logger.info(f"Found {len(members)} authorized members in {self.authorized_team}")
            return members

        except Exception as e:
            logger.exception(f"Error fetching authorized team members: {e}")
            self._authorized_members = []
            return []

    def _build_reply_map(self) -> Dict[int, List[Dict[str, Any]]]:
        """
        Build a map of comment_id -> list of replies.

        Fetches all PR comments once and organizes them by parent comment.
        This prevents N+1 API calls when checking feedback for multiple comments.

        Returns:
            Dict mapping comment_id to list of reply comment objects
        """
        reply_map = {}

        try:
            authorized_members = self._get_authorized_members()
            if not authorized_members:
                return reply_map

            replies_url = f"{self.base_url}/pulls/{self.pr_number}/comments"
            response = requests.get(replies_url, headers=self.headers)

            if response.status_code == 200:
                all_comments = response.json()
                logger.info(f"  Fetched {len(all_comments)} total PR comments for reply analysis")

                # Build map: comment_id -> [replies]
                for comment_data in all_comments:
                    parent_id = comment_data.get("in_reply_to_id")
                    if parent_id:
                        if parent_id not in reply_map:
                            reply_map[parent_id] = []
                        reply_map[parent_id].append(comment_data)
            else:
                logger.warning(f"Failed to fetch PR comments for reply map: {response.status_code}")

        except Exception as e:
            logger.warning(f"Error building reply map: {e}")

        return reply_map

    def _check_comment_feedback(self, comment: Comment, reply_map: Dict[int, List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Check if authorized users provided feedback (TP/FP) on this comment.

        Returns:
            Dict with feedback metadata:
            {
                "has_authorized_feedback": bool,
                "feedback_type": "TP" | "FP" | None,
                "feedback_author": str | None,
                "feedback_details": str | None
            }
        """
        feedback = {
            "has_authorized_feedback": False,
            "feedback_type": None,
            "feedback_author": None,
            "feedback_details": None
        }

        try:
            authorized_members = self._get_authorized_members()
            if not authorized_members:
                return feedback

            # Fetch comment reactions (thumbs up/down)
            reactions_url = f"{self.base_url}/pulls/comments/{comment.id}/reactions"
            response = requests.get(
                reactions_url,
                headers={**self.headers, "Accept": "application/vnd.github.squirrel-girl-preview+json"}
            )

            if response.status_code == 200:
                reactions = response.json()
                for reaction in reactions:
                    user = reaction.get("user", {}).get("login", "")
                    content = reaction.get("content", "")

                    if user in authorized_members:
                        if content == "+1":  # Thumbs up = True Positive
                            feedback["has_authorized_feedback"] = True
                            feedback["feedback_type"] = "TP"
                            feedback["feedback_author"] = user
                            feedback["feedback_details"] = f"{user} marked as True Positive (valid issue)"
                            logger.info(f"  ✓ TP feedback from {user} on comment {comment.id}")
                            break
                        elif content == "-1":  # Thumbs down = False Positive
                            feedback["has_authorized_feedback"] = True
                            feedback["feedback_type"] = "FP"
                            feedback["feedback_author"] = user
                            feedback["feedback_details"] = f"{user} marked as False Positive (invalid issue)"
                            logger.info(f"  ✗ FP feedback from {user} on comment {comment.id}")
                            break

            # Also check comment replies for explicit TP/FP markers
            if not feedback["has_authorized_feedback"] and reply_map is not None:
                # Use pre-fetched reply map instead of fetching all comments again (optimization)
                replies = reply_map.get(comment.id, [])

                for reply in replies:
                    reply_author = reply.get("user", {}).get("login", "")
                    reply_body = reply.get("body", "").lower()

                    if reply_author in authorized_members:
                        # Check for explicit TP/FP markers (use word boundaries to avoid false matches)
                        if re.search(r'\btp\b', reply_body) or "true positive" in reply_body or "valid issue" in reply_body:
                            feedback["has_authorized_feedback"] = True
                            feedback["feedback_type"] = "TP"
                            feedback["feedback_author"] = reply_author
                            feedback["feedback_details"] = f"{reply_author} confirmed as True Positive in reply"
                            logger.info(f"  ✓ TP feedback from {reply_author} via reply on comment {comment.id}")
                            break
                        elif re.search(r'\bfp\b', reply_body) or "false positive" in reply_body or "invalid" in reply_body or "not an issue" in reply_body:
                            feedback["has_authorized_feedback"] = True
                            feedback["feedback_type"] = "FP"
                            feedback["feedback_author"] = reply_author
                            feedback["feedback_details"] = f"{reply_author} marked as False Positive in reply"
                            logger.info(f"  ✗ FP feedback from {reply_author} via reply on comment {comment.id}")
                            break

        except Exception as e:
            logger.warning(f"Error checking feedback for comment {comment.id}: {e}")

        return feedback

    def _extract_from_ai_review(self, all_reviews: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Helper: Extract comments from the latest AI Code Review.

        I18N comments are posted as part of the AI Code Review.
        """

        # Filter for AI Code Reviews only
        ai_code_reviews = []
        for review in all_reviews:
            user_login = review.get("user", {}).get("login", "")
            review_body = review.get("body", "")

            # Check if it's from a bot
            is_bot = user_login.endswith("[bot]") or "bot" in user_login.lower()

            if not is_bot:
                continue

            # Identify review type
            review_type = identify_review_type(review_body)

            if review_type == ReviewType.AI_CODE_REVIEW:
                ai_code_reviews.append(review)
                logger.info(f"  ✓ AI Code Review #{review.get('id')} by {user_login}")
            else:
                logger.info(f"  ✗ Skipping {review_type.value} #{review.get('id')}")

        if not ai_code_reviews:
            logger.info(f"[{self.name}] No AI Code Review found")
            return []

        # Get latest AI Code Review
        ai_code_reviews.sort(key=lambda r: r.get("submitted_at", ""), reverse=True)
        latest_review = ai_code_reviews[0]

        logger.info(f"\n[{self.name}] Latest AI Code Review:")
        logger.info(f"  - Review ID: {latest_review.get('id')}")
        logger.info(f"  - Submitted: {latest_review.get('submitted_at')}")

        # Fetch comments from this review
        review_id = latest_review.get("id")
        return self._fetch_comments_from_review(review_id)

    def _fetch_comments_from_review(self, review_id: int) -> List[Dict[str, Any]]:
        """Fetch all comments from a specific review"""
        logger.info(f"\n[{self.name}] Fetching comments from review #{review_id}...")

        url = f"{self.base_url}/pulls/{self.pr_number}/comments"
        all_comments = []
        page = 1

        while True:
            response = requests.get(
                url,
                headers=self.headers,
                params={"page": page, "per_page": 100}
            )

            if response.status_code != 200:
                logger.error(f"[{self.name}] Error fetching comments: {response.status_code}")
                return all_comments

            comments = response.json()
            if not comments:
                break

            # Filter comments that belong to this review
            for comment in comments:
                if comment.get("pull_request_review_id") == review_id:
                    all_comments.append(comment)

            page += 1

        logger.info(f"[{self.name}] Fetched {len(all_comments)} comments from review #{review_id}")
        return all_comments

    def _filter_by_i18n_tag(self, comments: List[Dict[str, Any]]) -> List[Comment]:
        """
        Helper: Filter comments by [I18N, importance: X] tag format.
        """
        filtered = []

        for comment in comments:
            author = comment.get("user", {}).get("login", "")
            body = comment.get("body", "")

            # Match [I18N, importance: X] format (case insensitive)
            if re.search(r'\[I18N,\s*importance:\s*\d+\]', body, re.IGNORECASE):
                filtered.append(Comment(
                    id=comment.get("id"),
                    body=body,
                    author=author,
                    file_path=comment.get("path"),
                    line=comment.get("line"),
                    original_commit_id=comment.get("original_commit_id"),
                    commit_id=comment.get("commit_id"),
                    created_at=comment.get("created_at"),
                    updated_at=comment.get("updated_at"),
                    position=comment.get("position")
                ))

        logger.info(f"[{self.name}] Filtered {len(filtered)} I18N comments")
        return filtered

    def _apply_filters_and_score(self, comments: List[Comment]) -> List[Comment]:
        """
        Helper: Apply file filters and score comments by severity.

        Returns all comments (including excluded ones) with severity/category set.
        """

        # Apply file exclusion filters
        logger.info(f"  Applying file exclusion filters...")
        comments = self.file_filter.filter_comments(comments)

        # Extract severity and categorize
        logger.info(f"  Extracting severity and categorizing...")
        for i, comment in enumerate(comments):
            comment.severity = self._extract_severity(comment.body)
            comment.category = self._categorize_comment(comment.body)

            logger.info(f"    Comment #{i+1}: {comment.file_path}:{comment.line} | Severity: {comment.severity} | Category: {comment.category}")

        logger.info(f"  Scored {len(comments)} comments")
        return comments

    def _check_feedback_and_split(self, comments: List[Comment]) -> Tuple[List[Comment], List[Comment]]:
        """
        Helper: Check for authorized feedback and split comments.

        Returns:
            Tuple of (fp_comments, comments_to_analyze)
            - fp_comments: False Positives to auto-resolve without analysis
            - comments_to_analyze: Comments that need Claude analysis (TP + no feedback + pass filters)
        """
        # Check for authorized feedback on each comment
        logger.info(f"  Checking for authorized feedback from {self.authorized_team}...")

        # Fetch all PR comments once to build reply map (optimization to avoid N+1 queries)
        reply_map = self._build_reply_map()

        for comment in comments:
            feedback = self._check_comment_feedback(comment, reply_map)
            comment.has_authorized_feedback = feedback["has_authorized_feedback"]
            comment.feedback_type = feedback["feedback_type"]
            comment.feedback_author = feedback["feedback_author"]
            comment.feedback_details = feedback["feedback_details"]

            if comment.has_authorized_feedback:
                logger.info(f"    Comment {comment.id}: {comment.feedback_type} from {comment.feedback_author}")

        # Split into FP (auto-resolve) and comments needing analysis
        fp_filtered = []  # False Positives - auto-resolve without analysis
        tp_comments = []  # True Positives - require analysis
        no_feedback_comments = []  # No feedback - require analysis

        for comment in comments:
            if comment.has_authorized_feedback:
                if comment.feedback_type == "FP":
                    fp_filtered.append(comment)
                    logger.info(f"  ✓ FP: Auto-resolving comment {comment.id}")
                elif comment.feedback_type == "TP":
                    tp_comments.append(comment)
                    logger.info(f"  ⚠ TP: Keeping comment {comment.id} for analysis")
            else:
                no_feedback_comments.append(comment)

        logger.info(f"\n  Authorization filtering results:")
        logger.info(f"    - False Positives (auto-resolved): {len(fp_filtered)} comments")
        logger.info(f"    - True Positives (needs analysis): {len(tp_comments)} comments")
        logger.info(f"    - No feedback (needs analysis): {len(no_feedback_comments)} comments")

        # Apply severity threshold and file filters to comments needing analysis
        comments_to_filter = tp_comments + no_feedback_comments
        filtered = []
        excluded_count = 0

        for comment in comments_to_filter:
            if comment.excluded:
                excluded_count += 1
            elif comment.severity < self.severity_threshold:
                excluded_count += 1
            else:
                filtered.append(comment)

        logger.info(f"    - Excluded (file patterns or severity): {excluded_count} comments")
        logger.info(f"    - Passed filters (will analyze): {len(filtered)} comments")

        return fp_filtered, filtered

    def _analyze_with_claude(self, comments: List[Comment]) -> List[AnalysisResult]:
        """
        Helper: Analyze comments using Claude Code.

        Returns empty list if no comments to analyze.
        """
        if not comments:
            logger.info(f"  No comments to analyze")
            return []

        try:
            from src.services.comment_analyzer.claude_analyzer import ClaudeCommentAnalyzer

            logger.info(f"  Analyzing with Claude Code (skill: comment-analyzer)")

            analyzer = ClaudeCommentAnalyzer(
                github_token=self.github_token,
                repository=self.repository,
                pr_number=self.pr_number,
                skill_name="comment-analyzer",
                sub_agent_type=self.name
            )

            analysis_results = analyzer.analyze_comments(comments)

            # Convert to AnalysisResult objects
            results = []
            for analysis in analysis_results:
                comment = analysis["comment"]
                severity_level = self._map_importance_to_severity(comment.severity)

                result = AnalysisResult(
                    comment=comment,
                    addressed=analysis["addressed"],
                    confidence=analysis["confidence"],
                    reasoning=analysis["reasoning"],
                    severity_level=severity_level
                )
                results.append(result)

            logger.info(f"  Claude analysis complete: {len(results)} results")
            return results

        except Exception as e:
            logger.exception(f"  Error in Claude analysis: {e}")
            return self._fallback_analysis(comments)

    def _extract_severity(self, comment_body: str) -> int:
        """Extract severity from [I18N, importance: X] format"""
        pattern = r'\[I18N,\s*importance:\s*(\d+)\]'
        match = re.search(pattern, comment_body, re.IGNORECASE)
        return int(match.group(1)) if match else 5

    def _categorize_comment(self, comment_body: str) -> str:
        """Extract category from comment"""
        # Simple categorization based on keywords
        body_lower = comment_body.lower()
        if "currency" in body_lower or "symbol" in body_lower:
            return "i18n-Currency"
        elif "date" in body_lower or "time" in body_lower:
            return "i18n-DateTime"
        elif "phone" in body_lower or "number" in body_lower:
            return "i18n-PhoneNumber"
        elif "region" in body_lower or "country" in body_lower:
            return "i18n-Region"
        else:
            return "i18n-Other"

    def _map_importance_to_severity(self, importance: int) -> SeverityLevel:
        """Map importance score to severity level"""
        if importance >= 9:
            return SeverityLevel.CRITICAL
        elif importance >= 7:
            return SeverityLevel.HIGH
        elif importance >= 4:
            return SeverityLevel.MEDIUM
        else:
            return SeverityLevel.LOW

    def _fallback_analysis(self, comments: List[Comment]) -> List[AnalysisResult]:
        """Fallback analysis when Claude Code is unavailable"""
        logger.info(f"  Using fallback analysis (assume all unaddressed)")

        results = []
        for comment in comments:
            severity_level = self._map_importance_to_severity(comment.severity)

            result = AnalysisResult(
                comment=comment,
                addressed=False,
                confidence="low",
                reasoning=f"Fallback analysis - Claude Code unavailable",
                severity_level=severity_level
            )
            results.append(result)

        return results

    def _combine_results(self, analysis_results: List[AnalysisResult], fp_comments: List[Comment]) -> List[AnalysisResult]:
        """
        Helper: Combine Claude analysis results with FP auto-resolved comments.

        FP comments are marked as addressed with high confidence.
        """
        combined = list(analysis_results)

        if fp_comments:
            logger.info(f"  Adding {len(fp_comments)} FP auto-resolved comments to results")
            for fp_comment in fp_comments:
                severity_level = self._map_importance_to_severity(fp_comment.severity)

                fp_result = AnalysisResult(
                    comment=fp_comment,
                    addressed=True,  # Auto-resolved as FP
                    confidence="high",  # High confidence from authorized user
                    reasoning=f"Marked as False Positive by {fp_comment.feedback_author}. {fp_comment.feedback_details}",
                    severity_level=severity_level
                )
                combined.append(fp_result)
                logger.info(f"    ✓ FP: Comment {fp_comment.id} by {fp_comment.feedback_author}")

        return combined

    def _create_empty_result(self) -> 'SubAgentResult':
        """
        Helper: Create empty result when no comments found.
        """
        from src.services.comment_analyzer.sub_agent_base import SubAgentResult

        return SubAgentResult(
            sub_agent_name=self.name,
            status="PASS",
            total_comments=0,
            addressed=0,
            not_addressed=0,
            unaddressed_by_severity={"critical": 0, "high": 0, "medium": 0, "low": 0},
            critical_issues=[],
            addressed_comments=[],
            actions_executed=[]
        )

