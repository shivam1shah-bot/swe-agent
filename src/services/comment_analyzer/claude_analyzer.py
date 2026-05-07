"""
Claude Code-based comment analyzer.

Generic analyzer that uses Claude Code with specialized skills to analyze
if comments from different sub-agents have been addressed.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ClaudeCommentAnalyzer:
    """Generic comment analyzer using Claude Code with customizable skills."""

    def __init__(
        self,
        github_token: str,
        repository: str,
        pr_number: int,
        skill_name: str = "comment-analyzer",
        sub_agent_type: str = "i18n"
    ):
        """
        Initialize Claude analyzer.

        Args:
            github_token: GitHub authentication token
            repository: Repository in owner/repo format
            pr_number: PR number
            skill_name: Name of the skill to use (directory name in .claude/skills/)
                        Default is "comment-analyzer" which is generic for all sub-agent types
            sub_agent_type: Type of sub-agent (i18n, security, performance, code_quality, style, bug, accessibility, etc.)
        """
        self.github_token = github_token
        self.repository = repository
        self.pr_number = pr_number
        self.skill_name = skill_name
        self.sub_agent_type = sub_agent_type

        # Reference the skill from .claude/skills directory
        self.skill_path = (
            Path(__file__).parent.parent.parent.parent / ".claude" / "skills" /
            skill_name / "SKILL.md"
        )

        # Validate skill exists
        if not self.skill_path.exists():
            raise ValueError(f"Skill not found: {skill_name} at {self.skill_path}")

    def analyze_comments(self, comments: List[Any]) -> List[Dict[str, Any]]:
        """
        Analyze a batch of comments using Claude Code.

        Args:
            comments: List of comment objects with body, file_path, severity, category

        Returns:
            List of analysis results
        """
        if not comments:

            logger.info("No comments to analyze")
            return []

        logger.info(f"Starting comment analysis for {self.repository}#{self.pr_number}")
        logger.info(f"Sub-agent type: {self.sub_agent_type}")
        logger.info(f"Skill: {self.skill_name}")
        logger.info(f"Total comments to analyze: {len(comments)}")

        try:
            # Load the skill prompt template
            with open(self.skill_path, 'r') as f:
                skill_template = f.read()

            logger.info(f"Loaded s"
                        f"kill template from: {self.skill_path}")
            logger.info(f"Template size: {len(skill_template)} characters")

            # Prepare comment data with full GitHub metadata
            comments_data = []
            for i, comment in enumerate(comments):
                comment_data = {
                    "id": comment.id,
                    "comment_number": i + 1,
                    "body": comment.body,
                    "file_path": comment.file_path or "Unknown",
                    "line": comment.line,
                    "severity": comment.severity,
                    "category": comment.category,
                    # GitHub metadata for context analysis
                    "original_commit_id": getattr(comment, 'original_commit_id', None),
                    "commit_id": getattr(comment, 'commit_id', None),
                    "created_at": getattr(comment, 'created_at', None),
                    "updated_at": getattr(comment, 'updated_at', None),
                    "position": getattr(comment, 'position', None),
                    # Authorization feedback from authorized team members
                    "has_authorized_feedback": getattr(comment, 'has_authorized_feedback', False),
                    "feedback_type": getattr(comment, 'feedback_type', None),
                    "feedback_author": getattr(comment, 'feedback_author', None),
                    "feedback_details": getattr(comment, 'feedback_details', None),
                }
                comments_data.append(comment_data)

                logger.info(f"\n--- Comment #{i+1} ---")
                logger.info(f"ID: {comment.id}")
                logger.info(f"File: {comment.file_path}:{comment.line}")
                logger.info(f"Severity: {comment.severity}")
                logger.info(f"Category: {comment.category}")
                if getattr(comment, 'has_authorized_feedback', False):
                    logger.info(f"Authorized Feedback: {comment.feedback_type} from {comment.feedback_author}")
                logger.info(f"Created: {comment_data.get('created_at', 'N/A')}")
                logger.info(f"Commit: {comment_data.get('commit_id', 'N/A')[:8] if comment_data.get('commit_id') else 'N/A'}")
                logger.info(f"Body preview: {comment.body[:150]}...")

            # Substitute placeholders in the skill template
            prompt = skill_template.replace("{{REPOSITORY}}", self.repository)
            prompt = prompt.replace("{{PR_NUMBER}}", str(self.pr_number))
            prompt = prompt.replace("{{SUB_AGENT_TYPE}}", self.sub_agent_type)
            prompt = prompt.replace("{{COMMENTS_JSON}}", json.dumps(comments_data, indent=2))

            logger.info(f"\nFinal prompt size: {len(prompt)} characters")
            logger.info(f"Executing Claude Code analysis...")

            # Execute Claude Code
            result = self._execute_claude_code(prompt)

            # Log detailed response structure for debugging
            logger.info(f"Claude Code execution complete")
            logger.info(f"Result keys: {list(result.keys())}")
            raw_response = result.get("raw_response", {})
            if raw_response:
                logger.info(f"Raw response keys: {list(raw_response.keys())}")
                logger.info(f"Is error: {raw_response.get('is_error', 'N/A')}")
                logger.info(f"Stop reason: {raw_response.get('stop_reason', 'N/A')}")
                logger.info(f"Num turns: {raw_response.get('num_turns', 'N/A')}")

            # Parse the response
            analysis_results = self._parse_claude_response(result, comments)

            logger.info(f"Analysis complete. Processed {len(analysis_results)} results")
            return analysis_results

        except Exception as e:
            logger.exception(f"Error analyzing comments with Claude: {e}")
            return self._fallback_analysis(comments)

    def _execute_claude_code(self, prompt: str) -> Dict[str, Any]:
        """Execute Claude Code with the analysis prompt."""
        try:
            import tempfile
            from pathlib import Path
            from src.agents.terminal_agents.claude_code import ClaudeCodeTool

            # Get Claude Code instance
            claude_tool = ClaudeCodeTool.get_instance()

            # Create temporary output file for stream-json format (verbose execution logs)
            output_file = tempfile.mktemp(suffix=f"_comment_analysis_{self.sub_agent_type}.jsonl")
            logger.info(f"Using stream-json output file for execution visibility: {output_file}")

            # Set up execution parameters with output file for verbose logging
            params = {
                "action": "run_prompt",
                "prompt": prompt,
                "agent_name": f"{self.sub_agent_type}_comment_analyzer",
                "output_file": output_file,  # Enable stream-json format for turn-by-turn logs
            }

            # Execute synchronously
            result = claude_tool.execute_sync(params)

            # Log execution summary
            logger.info(f"Claude Code execution completed")

            # Parse and log execution details from stream-json file
            if Path(output_file).exists():
                self._log_execution_details(output_file)

            return result

        except Exception as e:
            logger.exception(f"Error executing Claude Code: {e}")
            return {"error": str(e)}

    def _log_execution_details(self, output_file: str):
        """Parse stream-json output and log execution details for visibility."""
        import json
        from pathlib import Path

        try:
            logger.info(f"\n{'='*80}")
            logger.info(f"Claude Code Execution Trace (Tool Calls)")
            logger.info(f"{'='*80}")

            tool_calls = []
            turn_count = 0

            with open(output_file, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        event = json.loads(line.strip())
                        event_type = event.get('type', 'unknown')

                        # Stream-json format: {"type": "assistant", "message": {"content": [...]}}
                        if event_type == 'assistant':
                            turn_count += 1
                            message = event.get('message', {})
                            content_items = message.get('content', [])

                            logger.info(f"\n--- Turn {turn_count} ---")

                            for item in content_items:
                                if isinstance(item, dict):
                                    item_type = item.get('type')

                                    if item_type == 'tool_use':
                                        tool_name = item.get('name', 'unknown')
                                        tool_input = item.get('input', {})

                                        logger.info(f"  🔧 Tool: {tool_name}")

                                        # Log Bash commands
                                        if tool_name == 'Bash':
                                            command = tool_input.get('command', '')
                                            desc = tool_input.get('description', '')
                                            logger.info(f"     Desc: {desc}")
                                            logger.info(f"     Cmd: {command[:300]}")

                                        # Log Read operations
                                        elif tool_name == 'Read':
                                            file_path = tool_input.get('file_path', '')
                                            logger.info(f"     File: {file_path}")

                                        # Log Grep operations
                                        elif tool_name == 'Grep':
                                            pattern = tool_input.get('pattern', '')
                                            path = tool_input.get('path', '.')
                                            logger.info(f"     Pattern: {pattern}")
                                            logger.info(f"     Path: {path}")

                                        # Track for summary
                                        tool_calls.append({
                                            'turn': turn_count,
                                            'tool': tool_name,
                                            'input': tool_input
                                        })

                                    elif item_type == 'text':
                                        text_content = item.get('text', '')[:150]
                                        if text_content.strip():
                                            logger.info(f"  💭 Response: {text_content}...")

                        # Log tool results
                        elif event_type == 'tool_result':
                            content = event.get('content', '')
                            if isinstance(content, str):
                                preview = content[:200]
                            else:
                                preview = str(content)[:200]
                            logger.info(f"  ✅ Result: {preview}...")

                    except json.JSONDecodeError:
                        continue

            # Summary
            logger.info(f"\n{'='*80}")
            logger.info(f"Execution Summary:")
            logger.info(f"  Total Turns: {turn_count}")
            logger.info(f"  Tool Calls: {len(tool_calls)}")

            # Group by tool type
            tool_counts = {}
            for call in tool_calls:
                tool = call['tool']
                tool_counts[tool] = tool_counts.get(tool, 0) + 1

            logger.info(f"  Tools Used:")
            for tool, count in tool_counts.items():
                logger.info(f"    - {tool}: {count}x")

            logger.info(f"{'='*80}\n")

        except Exception as e:
            logger.warning(f"Could not parse execution details: {e}")
            import traceback
            logger.warning(traceback.format_exc())

    def _parse_claude_response(
        self, result: Dict[str, Any], comments: List[Any]
    ) -> List[Dict[str, Any]]:
        """Parse Claude Code response and map to comment analysis results."""

        # Check if there was an error in the raw response
        raw_response = result.get("raw_response", {})
        if raw_response.get("is_error"):
            error_msg = raw_response.get("result", "Unknown error")
            logger.error(f"Claude Code execution failed: {error_msg}")
            return self._fallback_analysis(comments)

        # Check for error in the top-level result
        if result.get("error"):
            logger.error(f"Claude Code execution error: {result.get('error')}")
            return self._fallback_analysis(comments)

        try:
            # Get the response text from the "result" field
            response_text = result.get("result", "")

            # Extract JSON from markdown code blocks if present
            json_text = self._extract_json_from_response(response_text)

            # Parse JSON
            analysis_results = json.loads(json_text)

            if not isinstance(analysis_results, list):
                logger.error("Claude response is not a list")
                return self._fallback_analysis(comments)

            # Map results to comments
            return self._map_results_to_comments(analysis_results, comments)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON: {e}")
            logger.error(f"Response text: {response_text[:500]}")
            return self._fallback_analysis(comments)
        except Exception as e:
            logger.exception(f"Error parsing Claude response: {e}")
            return self._fallback_analysis(comments)

    def _extract_json_from_response(self, response_text: str) -> str:
        """Extract JSON from response, handling markdown code blocks."""
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            return response_text[json_start:json_end].strip()
        elif "```" in response_text:
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            return response_text[json_start:json_end].strip()
        else:
            # Try to find JSON array brackets
            start = response_text.find("[")
            end = response_text.rfind("]")
            if start != -1 and end != -1:
                return response_text[start:end+1].strip()
            return response_text.strip()

    def _map_results_to_comments(
        self, analysis_results: List[Dict], comments: List[Any]
    ) -> List[Dict[str, Any]]:
        """Map analysis results to comment objects."""
        logger.info(f"\n{'='*80}")
        logger.info(f"Mapping {len(analysis_results)} analysis results to comments")
        logger.info(f"{'='*80}")

        mapped_results = []

        for idx, analysis in enumerate(analysis_results):
            # Find matching comment
            comment_id = analysis.get("comment_id")
            matching_comment = next(
                (c for c in comments if c.id == comment_id), None
            )

            if matching_comment:
                result = {
                    "comment": matching_comment,
                    "addressed": analysis.get("addressed", False),
                    "confidence": analysis.get("confidence", "low"),
                    "reasoning": analysis.get("reasoning", ""),
                    "severity": analysis.get("severity", "medium"),
                    "category": analysis.get("category", "other"),
                }
                mapped_results.append(result)

                # Log detailed per-comment analysis
                logger.info(f"\n--- Analysis Result #{idx+1} ---")
                logger.info(f"Comment ID: {comment_id}")
                logger.info(f"File: {matching_comment.file_path}:{matching_comment.line}")
                logger.info(f"Category: {result['category']}")
                logger.info(f"Severity: {result['severity']}")
                logger.info(f"Addressed: {result['addressed']}")
                logger.info(f"Confidence: {result['confidence']}")
                logger.info(f"Reasoning: {result['reasoning']}")
            else:
                logger.warning(f"No matching comment for ID: {comment_id}")

        # Add fallback for any comments not analyzed
        analyzed_ids = {r["comment"].id for r in mapped_results}
        for comment in comments:
            if comment.id not in analyzed_ids:
                logger.warning(f"\n--- Missing Analysis for Comment {comment.id} ---")
                logger.warning(f"File: {comment.file_path}:{comment.line}")
                logger.warning(f"Using fallback: marked as NOT ADDRESSED")

                mapped_results.append({
                    "comment": comment,
                    "addressed": False,
                    "confidence": "low",
                    "reasoning": "Not analyzed by Claude",
                    "severity": "medium",
                    "category": "other",
                })

        logger.info(f"\n{'='*80}")
        logger.info(f"Mapping complete: {len(mapped_results)} total results")
        logger.info(f"{'='*80}\n")

        return mapped_results

    def _fallback_analysis(self, comments: List[Any]) -> List[Dict[str, Any]]:
        """Fallback analysis when Claude Code fails - assume all not addressed."""
        return [
            {
                "comment": comment,
                "addressed": False,
                "confidence": "low",
                "reasoning": "Fallback analysis - Claude Code unavailable",
                "severity": "medium",
                "category": comment.category or "other",
            }
            for comment in comments
        ]
