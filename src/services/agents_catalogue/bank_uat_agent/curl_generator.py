"""
Curl Command Generator for Bank UAT Agent

This module handles intelligent generation of comprehensive curl commands
from API documentation for UAT testing scenarios. Designed to be bank-agnostic
and rely on AI for context-aware generation rather than hardcoded patterns.
"""

import json
import re
from typing import Dict, Any, List, Optional

from src.providers.context import Context
from src.providers.logger import Logger


class CurlCommandGenerator:
    """
    Intelligent curl command generator for comprehensive UAT testing
    
    Features:
    - API documentation parsing and URL extraction
    - AI-powered context-aware generation
    - Multi-scenario test generation (success, error, boundary, security)
    - Custom header and parameter support
    - Bank-agnostic design for universal compatibility
    """

    def __init__(self, logger: Optional[Logger] = None):
        """Initialize curl generator with optional logger"""
        self.logger = logger or Logger()

    def extract_urls_from_documentation(self, api_doc_content: str, bank_name: str, uat_host: str,
                                        apis_to_test: Optional[List[str]] = None, ctx: Optional[Context] = None) -> \
            Dict[str, str]:
        """
        Extract API URLs from documentation and apply UAT host
        
        Args:
            api_doc_content: API documentation content as string
            bank_name: Name of the bank
            uat_host: UAT host URL to use
            apis_to_test: Optional list of specific APIs to extract
            ctx: Optional context for AI operations
            
        Returns:
            Dictionary mapping API names to complete URLs
        """
        self.logger.info(f"🔍 Starting URL extraction for {bank_name}")
        self.logger.info(f"  UAT Host: {uat_host}")
        self.logger.info(f"  APIs to test: {apis_to_test if apis_to_test else 'All available'}")

        # Log document content analysis
        content_length = len(api_doc_content) if api_doc_content else 0
        self.logger.info(f"📄 Document Content Analysis:")
        self.logger.info(f"  Content length: {content_length} characters")
        self.logger.info(f"  Content is empty: {not api_doc_content or not api_doc_content.strip()}")

        if api_doc_content and api_doc_content.strip():
            # Show content preview for debugging
            content_preview = api_doc_content[:300]
            self.logger.info(f"  Content preview (first 300 chars): {content_preview}...")

            # Analyze content structure
            lines = api_doc_content.strip().split('\n')
            non_empty_lines = [line for line in lines if line.strip()]
            self.logger.info(f"  Total lines: {len(lines)}")
            self.logger.info(f"  Non-empty lines: {len(non_empty_lines)}")

            # Look for common API documentation patterns
            patterns_found = []
            if 'endpoint' in api_doc_content.lower():
                patterns_found.append('endpoint references')
            if 'url' in api_doc_content.lower():
                patterns_found.append('URL references')
            if 'http' in api_doc_content.lower():
                patterns_found.append('HTTP URLs')
            if 'post' in api_doc_content.lower() or 'get' in api_doc_content.lower():
                patterns_found.append('HTTP methods')

            self.logger.info(f"  Patterns found: {patterns_found if patterns_found else 'None detected'}")
        else:
            self.logger.error("❌ API documentation content is empty or None!")
            self.logger.error("  This is likely why URL extraction is failing")
            return {}

        try:
            self.logger.info("🤖 Attempting AI-based URL extraction...")
            extracted_urls = self._extract_urls_with_ai_only(
                api_doc_content, bank_name, uat_host, apis_to_test, ctx
            )

            if extracted_urls:
                self.logger.info(f"✅ AI extraction successful: {len(extracted_urls)} URLs found")
                return extracted_urls

            return {}
        except Exception as e:
            self.logger.error(f"❌ URL extraction failed: {str(e)}")
            return {}

    def generate_curl_commands(
            self,
            urls: Dict[str, str],
            api_doc_content: str,
            bank_name: str,
            custom_headers: Optional[Dict[str, str]] = None,
            custom_prompt: Optional[str] = None,
            encryption_context: Optional[Dict[str, Any]] = None,
            ctx: Optional[Context] = None
    ) -> List[str]:
        """
        Generate comprehensive curl commands with multiple variations for UAT testing
        
        Args:
            urls: Dictionary of URLs to test
            api_doc_content: API documentation content
            bank_name: Bank name for context
            custom_headers: Optional custom headers
            custom_prompt: Optional custom requirements
            encryption_context: Optional encryption context for curl generation
            ctx: Context for autonomous agent calls
            
        Returns:
            List of generated curl commands with variations
        """
        self.logger.info(f"Generating curl commands with variations for {len(urls)} URLs")
        all_curls = []
        curl_counter = 1

        for url_name, url in urls.items():
            self.logger.info(f"Generating curl #{curl_counter} for {url_name}: {url}")

            # Generate 3 variations for each URL
            for variation in range(1, 4):
                self.logger.info(f"  Generating variation {variation} for curl #{curl_counter}")

                # Generate curl variation using AI agent
                variation_curl = self._generate_curl_variation(
                    url_name=url_name,
                    url=url,
                    api_doc_content=api_doc_content,
                    bank_name=bank_name,
                    variation_number=variation,
                    custom_headers=custom_headers,
                    custom_prompt=custom_prompt,
                    ctx=ctx
                )

                if variation_curl:
                    self.logger.info(f"  ✅ Generated variation {variation} for curl #{curl_counter}")
                    all_curls.append(variation_curl)
                else:
                    self.logger.warning(f"  ❌ Failed to generate variation {variation} for curl #{curl_counter}")

            curl_counter += 1

        self.logger.info(f"Generated {len(all_curls)} total curl command variations")
        return all_curls

    def _generate_curl_variation(
            self,
            url_name: str,
            url: str,
            api_doc_content: str,
            bank_name: str,
            variation_number: int,
            custom_headers: Optional[Dict[str, str]],
            custom_prompt: Optional[str],
            ctx: Optional[Context]
    ) -> Optional[str]:
        """Generate a single curl variation for a specific URL"""

        # Define variation types
        variation_types = {
            1: {
                'name': 'valid_request',
                'description': 'Valid request with proper parameters and realistic test data',
                'focus': 'Generate a valid, successful request with complete and realistic payload data'
            },
            2: {
                'name': 'error_handling',
                'description': 'Invalid request to test error handling scenarios',
                'focus': 'Generate an invalid request to test error responses (missing fields, wrong types, etc.)'
            },
            3: {
                'name': 'edge_cases',
                'description': 'Edge case testing with boundary values',
                'focus': 'Generate requests with edge cases like empty values, max lengths, special characters'
            }
        }

        variation_config = variation_types.get(variation_number, variation_types[1])

        # Build headers
        headers = self._build_headers(bank_name, custom_headers)

        # Build variation-specific prompt
        prompt = f"""
Generate a single curl command for testing this {bank_name} API endpoint.
VARIATION TYPE: {variation_config['name'].upper()}
FOCUS: {variation_config['focus']}

CRITICAL: YOU MUST FOLLOW THIS EXACT FORMAT - NO EXCEPTIONS

REQUIRED OUTPUT FORMAT:
Return exactly ONE curl command wrapped in a curl block like this:

MANDATORY FORMATTING RULES:
1. Return ONLY ONE curl command
2. Start with ```
3. End with ```
4. Strictly - NO new line or No line break
5. Use single quotes for JSON payloads
6. Keep JSON payloads on a single line
7. Make the payload realistic and complete (no placeholder text)
8. Use appropriate HTTP method (POST/PUT/GET/DELETE) based on endpoint purpose
9. Strictly Pick the request payload from the API documentation and make it realistic and complete (no placeholder text)
10. IMPORTANT: Add required headers where specified in the API documentation (Authentication, Content-Type, Accept, User-Agent, etc.)

Endpoint Details:
- URL: {url}
- URL Name: {url_name}
- Variation: ({variation_config['name']})

Required Headers:
{', '.join([f'{k}: {v}' for k, v in headers.items()])}

**Specific Requirements for this variation:
- {variation_config['description']}
- {variation_config['focus']}
- Include realistic test data appropriate for {bank_name}
- Make the request specific to the '{url_name}' endpoint purpose
- MUST include all necessary headers as specified in the API documentation
- Add authentication headers if required by the endpoint
- Include Content-Type and Accept headers for POST/PUT requests
- Add any custom headers mentioned in the API documentation

Custom Requirements: {custom_prompt or 'None'}

REMEMBER: Return exactly ONE curl command in the specified format, plain text, no new line, no additional text or explanation.**
The curl should be complete and executable with all required headers included.

API Documentation Context:
{api_doc_content}
"""

        try:
            self.logger.info(f"Calling AI agent for {url_name} variation {variation_number}")
            agent_result = self._call_autonomous_agent(prompt, ctx)

            if agent_result.get("success", False):
                response_content = agent_result.get("result", "")
                self.logger.info(f"AI response for {url_name} variation {variation_number}: {response_content}")

                # Extract single curl command from response
                extracted_curl = self._extract_single_curl_from_response(response_content)

                if extracted_curl:
                    self.logger.info(f"Successfully extracted curl for {url_name} variation {variation_number}")
                    return extracted_curl
                else:
                    self.logger.warning(
                        f"Failed to extract curl from response for {url_name} variation {variation_number}")
                    return None
            else:
                self.logger.warning(f"AI agent failed for {url_name} variation {variation_number}")
                return None

        except Exception as e:
            self.logger.error(f"Error generating curl variation {variation_number} for {url_name}: {str(e)}")
            return None

    def _extract_single_curl_from_response(
            self,
            response_content
    ) -> Optional[str]:
        """Extract a single curl command from AI response"""
        try:
            # Handle case where response_content might be a dictionary
            if isinstance(response_content, dict):
                self.logger.info(f"Response content is dict, extracting string content")
                # Try to extract content from common keys
                if "content" in response_content:
                    response_content = response_content["content"]
                elif "result" in response_content:
                    response_content = response_content["result"]
                else:
                    response_content = str(response_content)
                self.logger.info(f"Extracted content: {response_content}")
            
            # Ensure response_content is a string
            if not isinstance(response_content, str):
                response_content = str(response_content)
            
            # Look for curl code blocks - try multiple patterns
            curl_patterns = [
                r'```curl\s*(curl.*?)```',  # Pattern for ```curl ... ``` keeping 'curl'
                r'```\s*curl\s*(curl.*?)```',  # Pattern allowing space before curl, keeping 'curl'
                r'```\s*(curl.*?)```',  # Pattern with curl as first word, keeping 'curl'
            ]
            
            curl_command = None
            for pattern in curl_patterns:
                matches = re.findall(pattern, response_content, re.DOTALL)
                if matches:
                    curl_command = matches[0].strip()
                    self.logger.info(f"Found curl command using pattern: {pattern}")
                    break

            if curl_command:
                # Clean up the curl command
                cleaned_curl = self._clean_curl_format(curl_command)

                if cleaned_curl:
                    self.logger.raw_info(f"Extracted curl command: {cleaned_curl}")
                    return cleaned_curl
                else:
                    self.logger.warning("Curl command cleaning failed")
                    return None
            else:
                self.logger.warning("No curl code blocks found in response")
                self.logger.info(f"Response content for debugging: {response_content[:500]}...")
                return None

        except Exception as e:
            self.logger.error(f"Error extracting curl from response: {str(e)}")
            return None

    def _extract_urls_with_ai_only(
            self,
            api_doc_content: str,
            bank_name: str,
            uat_host: str,
            apis_to_test: Optional[List[str]] = None,
            ctx: Optional[Context] = None
    ) -> Dict[str, str]:
        """
        Extract URLs using AI only (following UAT_LangGraph pattern)
        
        Args:
            api_doc_content: API documentation content
            bank_name: Bank name for context enhancement
            uat_host: UAT environment host URL
            apis_to_test: Optional list of specific APIs to focus on
            ctx: Context for autonomous agent calls
            
        Returns:
            Dictionary of {url_name: url} pairs
        """
        self.logger.info(f"Using AI to extract URLs from documentation for {bank_name}")

        try:
            # UAT host context
            uat_context = ""
            if uat_host:
                uat_context = f"\nUAT Environment Host: {uat_host}"
                uat_context += "\nNote: Combine endpoint paths with the base URL or UAT host to create complete URLs."

            # Create focused prompt following UAT_LangGraph pattern
            prompt = f"""
Extract the API endpoints from the documentation for {bank_name} and create complete URLs.
{uat_context}

LOOK FOR:
1. Endpoint paths (like POST /balance_inquiry, GET /transaction_status)
2. Base URLs (like https://api.example.com/v1)
3. API endpoint descriptions

CREATE COMPLETE URLs by combining base URLs with endpoint paths.

Return the result in this exact JSON format:
{{"API_NAME": "PATH"}}

EXAMPLE:
{{"balance_inquiry": "https://uat-api.testbank.com/v1/balance_inquiry","fund_transfer": "https://uat-api.testbank.com/v1/fund_transfer","transaction_status": "https://uat-api.testbank.com/v1/transaction_status"}}

IMPORTANT: 
- Donot use new line or line breaks
- Return ONLY the JSON object, no additional text
- Use descriptive names as keys (like "balance_inquiry", "fund_transfer")
- Ensure URLs are complete with protocol and host
- Include all available endpoints from the documentation

API Documentation:
{api_doc_content}
"""

            # Call autonomous agent
            agent_result = self._call_autonomous_agent(prompt, ctx)
            self.logger.info(f"Agent result success: {agent_result.get('success', False)}")
            self.logger.info(f"Agent result error: {agent_result.get('error', 'No error')}")

            if agent_result.get("success", False):
                response_content = agent_result.get("result", "")

                # Handle nested content structure
                if isinstance(response_content, dict):
                    if "result" in response_content:
                        actual_content = response_content["result"]
                        self.logger.info(f"Extracted 'result' field from response: {actual_content}")
                        response_content = actual_content
                    elif "content" in response_content:
                        actual_content = response_content["content"]
                        self.logger.info(f"Extracted 'content' field from response: {actual_content}")
                        response_content = actual_content

                # Also handle string responses that might contain JSON
                if isinstance(response_content, str) and response_content.startswith('{'):
                    try:
                        parsed_response = json.loads(response_content)
                        if isinstance(parsed_response, dict):
                            if "result" in parsed_response:
                                actual_content = parsed_response["result"]
                                self.logger.info(
                                    f"Parsed string response and extracted 'result' field: {actual_content}")
                                response_content = actual_content
                            elif "content" in parsed_response:
                                actual_content = parsed_response["content"]
                                self.logger.info(
                                    f"Parsed string response and extracted 'content' field: {actual_content}")
                                response_content = actual_content
                    except json.JSONDecodeError:
                        self.logger.info("String response is not JSON, treating as regular content")

                extracted_urls = self._extract_json_from_response(response_content)
                self.logger.info(f"Parsed URLs: {extracted_urls}")
                return extracted_urls
            else:
                error_msg = agent_result.get('error', 'Unknown error')
                self.logger.warning(f"AI URL extraction failed: {error_msg}")

        except Exception as e:
            self.logger.error(f"AI URL extraction failed with exception: {str(e)}")

        return {}

    def _apply_uat_host_to_urls(self, urls: Dict[str, str], uat_host: str) -> Dict[str, str]:
        """
        Apply UAT host to URLs that don't have a complete host
        
        Args:
            urls: Dictionary of URLs
            uat_host: UAT host URL
            
        Returns:
            Updated URLs with UAT host applied where needed
        """
        updated_urls = {}

        # Clean up UAT host (remove trailing slash)
        uat_host = uat_host.rstrip('/')

        for url_name, url in urls.items():
            # Check if URL already has a protocol and host
            if url.startswith('http://') or url.startswith('https://'):
                # URL is complete, use as-is
                updated_urls[url_name] = url
            elif url.startswith('/'):
                # URL is a path, prepend UAT host
                updated_urls[url_name] = f"{uat_host}{url}"
            else:
                # URL might be relative or incomplete, try to combine
                if '://' not in url:
                    # Doesn't have protocol, treat as path
                    path = url if url.startswith('/') else f"/{url}"
                    updated_urls[url_name] = f"{uat_host}{path}"
                else:
                    # Has protocol but might be malformed, use as-is
                    updated_urls[url_name] = url

        self.logger.info(f"Applied UAT host {uat_host} to URLs where needed")
        return updated_urls

    def _build_headers(self, bank_name: str, custom_headers: Optional[Dict[str, str]]) -> Dict[str, str]:
        """Build generic headers for API testing"""
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json',
                   'User-Agent': f'UAT-Test-Client/1.0', 'Authorization': 'Bearer test_token_123456789'}

        # Add standard authorization header

        # Add custom headers (these can override the defaults)
        if custom_headers:
            headers.update(custom_headers)

        return headers

    def _call_autonomous_agent(self, prompt: str, ctx: Optional[Context]) -> Dict[str, Any]:
        """Call autonomous agent with the given prompt"""
        try:
            from src.agents.autonomous_agent import AutonomousAgentTool

            agent_tool = AutonomousAgentTool()
            result = agent_tool.execute({
                "prompt": prompt,
                "task_id": ctx.get("task_id") if ctx else "curl-gen",
                "agent_name": "bank-uat-agent",
            })

            self.logger.raw_info(f'{result}')

            return result

        except Exception as e:
            self.logger.error(f"Autonomous agent execution failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "result": None
            }

    def _extract_json_from_response(self, response_content) -> Dict[str, str]:
        """
        Extract JSON from autonomous agent response
        
        Args:
            response_content: Raw response content from agent (string or dict)
            
        Returns:
            Parsed JSON as dictionary
        """
        try:
            # Handle different input types
            if isinstance(response_content, dict):
                # If it's already a dictionary, check if it contains the URLs we need
                if all(isinstance(value, str) and value.startswith('http') for value in response_content.values()):
                    self.logger.info("Response is already a valid URL dictionary")
                    return response_content
                else:
                    # Convert dictionary to string for processing
                    response_content = str(response_content)
                    self.logger.info("Converted dictionary response to string for JSON extraction")

            # Ensure we have a string to work with
            if not isinstance(response_content, str):
                error_msg = f"Expected string response, got {type(response_content)}"
                self.logger.error(error_msg)
                raise ValueError(error_msg)

            # Clean up the response content
            cleaned_content = response_content.strip()
            self.logger.info(f"Cleaned content length: {len(cleaned_content)} characters")
            self.logger.info(f"Full cleaned content: {cleaned_content}")

            # Strategy 1: Look for JSON code blocks (```json ... ```)
            json_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', cleaned_content, re.DOTALL)
            if json_block_match:
                json_content = json_block_match.group(1)
                self.logger.info(f"Found JSON code block, full extracted content: {json_content}")
                try:
                    parsed_json = json.loads(json_content)
                    if isinstance(parsed_json, dict):
                        self.logger.info(f"Successfully parsed JSON from code block: {len(parsed_json)} keys")
                        return parsed_json
                except json.JSONDecodeError as e:
                    self.logger.warning(f"JSON code block parsing failed: {e}")

            # Strategy 2: Look for nested content format like {'content': '{\n "fund_transfer_adhoc": "https://..."}'}
            nested_content_pattern = r"'content':\s*'(\{[^}]*\})'"
            nested_match = re.search(nested_content_pattern, cleaned_content)
            if nested_match:
                nested_json_str = nested_match.group(1)
                self.logger.info(f"Found nested content pattern, full extracted: {nested_json_str}")
                try:
                    # Clean up the nested JSON string
                    cleaned_nested = nested_json_str.replace("\\n", "").replace("\\'", "'").replace("\\\"", "\"")
                    parsed_json = json.loads(cleaned_nested)
                    if isinstance(parsed_json, dict):
                        self.logger.info(f"Successfully parsed nested content pattern: {len(parsed_json)} keys")
                        return parsed_json
                except json.JSONDecodeError as e:
                    self.logger.warning(f"Nested content pattern parsing failed: {e}")

            # Strategy 3: Look for JSON-like content between braces
            brace_match = re.search(r'(\{[^{}]*\})', cleaned_content)
            if brace_match:
                json_content = brace_match.group(1)
                self.logger.info(f"Found JSON-like content, full extracted: {json_content}")
                try:
                    parsed_json = json.loads(json_content)
                    if isinstance(parsed_json, dict):
                        self.logger.info(f"Successfully parsed JSON from braces: {len(parsed_json)} keys")
                        return parsed_json
                except json.JSONDecodeError as e:
                    self.logger.warning(f"JSON braces parsing failed: {e}")

            # Strategy 4: Try to parse the entire content as JSON
            self.logger.info("No JSON blocks or braces found, trying to parse entire content")
            try:
                parsed_json = json.loads(cleaned_content)
                if isinstance(parsed_json, dict):
                    self.logger.info(f"Successfully parsed entire content as JSON: {len(parsed_json)} keys")
                    return parsed_json
            except json.JSONDecodeError as json_error:
                self.logger.warning(f"Entire content JSON parsing failed: {json_error}")
                # Try cleaning up common issues
                cleaned_json = re.sub(r'[^\x20-\x7E]', '', cleaned_content)  # Remove non-printable chars
                try:
                    parsed_json = json.loads(cleaned_json)
                    if isinstance(parsed_json, dict):
                        self.logger.info(f"JSON parsing succeeded after cleanup: {len(parsed_json)} keys")
                        return parsed_json
                except json.JSONDecodeError as second_error:
                    self.logger.warning(f"JSON parsing still failed after cleanup: {second_error}")

            # Strategy 5: Try to extract just the JSON part
            json_start = cleaned_content.find('{')
            json_end = cleaned_content.rfind('}')
            if json_start != -1 and json_end != -1 and json_end > json_start:
                json_only = cleaned_content[json_start:json_end + 1]
                self.logger.info(f"Extracting JSON-only content, full content: {json_only}")
                try:
                    parsed_json = json.loads(json_only)
                    if isinstance(parsed_json, dict):
                        self.logger.info(f"Successfully parsed JSON-only content: {len(parsed_json)} keys")
                        return parsed_json
                except json.JSONDecodeError as e:
                    self.logger.warning(f"JSON-only parsing failed: {e}")

            # If all strategies fail, raise an error
            error_msg = "Could not extract valid JSON from response"
            self.logger.error(error_msg)
            self.logger.error(f"Final content that failed parsing: {cleaned_content}")
            raise ValueError(error_msg)

        except Exception as e:
            error_msg = f"Error extracting JSON from response: {str(e)}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)

    def _clean_curl_format(self, curl_command: str) -> str:
        """Clean up curl command format for better readability and execution"""
        # Remove extra whitespace and normalize line breaks
        lines = [line.strip() for line in curl_command.split('\n') if line.strip()]

        # Join lines with proper spacing
        cleaned_curl = ' '.join(lines)

        # Clean up multiple spaces
        cleaned_curl = ' '.join(cleaned_curl.split())

        # Ensure proper spacing around specific curl flags only (preserve hyphenated words)
        # Target specific curl flags: -H, -d, -X, -o, -v, etc.
        curl_flags = ['-H', '-d', '-X', '-o', '-v', '-u', '-k', '-L', '-s', '-S', '-f', '-i']
        for flag in curl_flags:
            # Add space before flag if there isn't one already
            pattern = r'(\w)(' + re.escape(flag) + r'\b)'
            cleaned_curl = re.sub(pattern, r'\1 \2', cleaned_curl)

        return cleaned_curl

    def _add_encryption_headers(self, curl_commands: List[str], encryption_context: Dict[str, Any]) -> List[str]:
        """Add encryption headers to curl commands without encrypting payload"""
        encryption_type = encryption_context.get('encryption_type', 'aes')
        enhanced_curls = []

        for curl in curl_commands:
            enhanced_curls.append(curl)

        return enhanced_curls
