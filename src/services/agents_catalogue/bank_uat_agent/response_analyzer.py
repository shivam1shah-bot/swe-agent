"""
Response Analyzer for Bank UAT Agent

This module provides comprehensive analysis of API responses including
validation, format detection, error analysis, and performance insights.
"""

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Union
from urllib.parse import urlparse

from src.providers.logger import Logger


class ResponseAnalyzer:
    """
    Comprehensive response analyzer for bank API UAT testing
    
    Features:
    - Response format detection (JSON, XML, HTML, text)
    - HTTP status code analysis
    - Error detection and categorization
    - Performance metrics analysis
    - Security validation
    - Bank-specific response pattern analysis
    """
    
    def __init__(self, logger: Optional[Logger] = None):
        """Initialize response analyzer with optional logger"""
        self.logger = logger or Logger()
        
        # Common bank API response patterns
        self.bank_patterns = {
            'success_indicators': [
                'success', 'completed', 'approved', 'accepted', 'ok', 'done',
                'transaction_id', 'reference_number', 'confirmation'
            ],
            'error_indicators': [
                'error', 'failed', 'rejected', 'denied', 'invalid', 'unauthorized',
                'timeout', 'expired', 'insufficient', 'blocked'
            ],
            'status_fields': [
                'status', 'result', 'response_code', 'return_code', 'error_code',
                'transaction_status', 'payment_status'
            ],
            'sensitive_fields': [
                'password', 'pin', 'token', 'key', 'secret', 'credential',
                'account_number', 'card_number', 'otp'
            ]
        }
        
        # HTTP status code mappings
        self.status_code_categories = {
            'success': range(200, 300),
            'redirect': range(300, 400),
            'client_error': range(400, 500),
            'server_error': range(500, 600)
        }
    
    def analyze_response(
        self,
        raw_response: str,
        decrypted_response: Optional[str],
        bank_name: str,
        request_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Perform comprehensive analysis of API response
        
        Args:
            raw_response: Raw response from the API
            decrypted_response: Decrypted response if encryption was used
            bank_name: Bank name for context-specific analysis
            request_metadata: Optional metadata about the request
            
        Returns:
            Comprehensive analysis results
        """
        self.logger.info(f"Analyzing response for {bank_name}")
        
        analysis = {
            "timestamp": datetime.now().isoformat(),
            "bank_name": bank_name,
            "raw_response_analysis": self._analyze_single_response(raw_response, "raw"),
            "decrypted_response_analysis": None,
            "comparison": None,
            "overall_assessment": {},
            "security_analysis": {},
            "recommendations": []
        }
        
        # Analyze decrypted response if available
        if decrypted_response and decrypted_response != raw_response:
            analysis["decrypted_response_analysis"] = self._analyze_single_response(
                decrypted_response, "decrypted"
            )
            analysis["comparison"] = self._compare_responses(raw_response, decrypted_response)
        
        # Perform overall assessment
        analysis["overall_assessment"] = self._assess_overall_quality(analysis, bank_name)
        
        # Security analysis
        analysis["security_analysis"] = self._analyze_security_aspects(analysis)
        
        # Generate recommendations
        analysis["recommendations"] = self._generate_recommendations(analysis, bank_name)
        
        return analysis
    
    def _analyze_single_response(self, response: str, response_type: str) -> Dict[str, Any]:
        """Analyze a single response (raw or decrypted)"""
        if not response or not response.strip():
            return {
                "type": response_type,
                "empty": True,
                "format": "none",
                "size": 0,
                "analysis": "Empty response"
            }
        
        response = response.strip()
        
        analysis = {
            "type": response_type,
            "empty": False,
            "size": len(response),
            "format": self._detect_response_format(response),
            "http_status": self._extract_http_status(response),
            "headers": self._extract_headers(response),
            "body": self._extract_body(response),
            "structure_analysis": {},
            "content_analysis": {},
            "error_analysis": {},
            "performance_indicators": {}
        }
        
        # Structure analysis based on format
        if analysis["format"] == "json":
            analysis["structure_analysis"] = self._analyze_json_structure(analysis["body"])
        elif analysis["format"] == "xml":
            analysis["structure_analysis"] = self._analyze_xml_structure(analysis["body"])
        elif analysis["format"] == "html":
            analysis["structure_analysis"] = self._analyze_html_structure(analysis["body"])
        
        # Content analysis
        analysis["content_analysis"] = self._analyze_content(analysis["body"])
        
        # Error analysis
        analysis["error_analysis"] = self._analyze_errors(response, analysis)
        
        # Performance indicators
        analysis["performance_indicators"] = self._extract_performance_indicators(response)
        
        return analysis
    
    def _detect_response_format(self, response: str) -> str:
        """Detect the format of the response"""
        response = response.strip()
        
        # Check for HTTP response
        if response.startswith('HTTP/'):
            # Extract body for format detection
            body_start = response.find('\r\n\r\n')
            if body_start != -1:
                body = response[body_start + 4:]
                return self._detect_body_format(body)
            return "http"
        
        return self._detect_body_format(response)
    
    def _detect_body_format(self, body: str) -> str:
        """Detect format of response body"""
        if not body.strip():
            return "empty"
        
        body = body.strip()
        
        # JSON detection
        if (body.startswith('{') and body.endswith('}')) or (body.startswith('[') and body.endswith(']')):
            try:
                json.loads(body)
                return "json"
            except:
                pass
        
        # XML detection
        if body.startswith('<') and body.endswith('>'):
            try:
                ET.fromstring(body)
                return "xml"
            except:
                pass
        
        # HTML detection
        if '<html' in body.lower() or '<body' in body.lower() or '<!doctype html' in body.lower():
            return "html"
        
        # Base64 detection (potential encrypted response)
        if re.match(r'^[A-Za-z0-9+/]*={0,2}$', body) and len(body) % 4 == 0 and len(body) > 20:
            return "base64"
        
        # Plain text
        return "text"
    
    def _extract_http_status(self, response: str) -> Optional[Dict[str, Any]]:
        """Extract HTTP status code and message"""
        if not response.startswith('HTTP/'):
            return None
        
        # Parse status line
        lines = response.split('\n')
        status_line = lines[0].strip()
        
        # Extract status code and message
        parts = status_line.split(' ', 2)
        if len(parts) >= 2:
            try:
                status_code = int(parts[1])
                status_message = parts[2] if len(parts) > 2 else ""
                
                # Categorize status code
                category = "unknown"
                for cat, code_range in self.status_code_categories.items():
                    if status_code in code_range:
                        category = cat
                        break
                
                return {
                    "code": status_code,
                    "message": status_message,
                    "category": category,
                    "success": category == "success"
                }
            except ValueError:
                pass
        
        return None
    
    def _extract_headers(self, response: str) -> Dict[str, str]:
        """Extract HTTP headers from response"""
        headers = {}
        
        if not response.startswith('HTTP/'):
            return headers
        
        lines = response.split('\n')
        header_section = True
        
        for line in lines[1:]:  # Skip status line
            line = line.strip()
            
            if not line:  # Empty line indicates end of headers
                break
            
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.strip().lower()] = value.strip()
        
        return headers
    
    def _extract_body(self, response: str) -> str:
        """Extract response body"""
        if not response.startswith('HTTP/'):
            return response
        
        # Find body after headers
        body_start = response.find('\r\n\r\n')
        if body_start == -1:
            body_start = response.find('\n\n')
        
        if body_start != -1:
            return response[body_start + 4:].strip() if '\r\n\r\n' in response else response[body_start + 2:].strip()
        
        return ""
    
    def _analyze_json_structure(self, body: str) -> Dict[str, Any]:
        """Analyze JSON response structure"""
        try:
            data = json.loads(body)
            
            analysis = {
                "valid_json": True,
                "type": type(data).__name__,
                "size": len(body),
                "structure": self._analyze_json_object(data),
                "fields": self._extract_json_fields(data)
            }
            
            return analysis
            
        except json.JSONDecodeError as e:
            return {
                "valid_json": False,
                "error": str(e),
                "size": len(body)
            }
    
    def _analyze_json_object(self, obj: Any, max_depth: int = 3, current_depth: int = 0) -> Dict[str, Any]:
        """Recursively analyze JSON object structure"""
        if current_depth >= max_depth:
            return {"truncated": True, "type": type(obj).__name__}
        
        if isinstance(obj, dict):
            return {
                "type": "object",
                "keys": list(obj.keys()),
                "key_count": len(obj),
                "nested_objects": {
                    k: self._analyze_json_object(v, max_depth, current_depth + 1)
                    for k, v in obj.items()
                    if isinstance(v, (dict, list))
                }
            }
        elif isinstance(obj, list):
            return {
                "type": "array",
                "length": len(obj),
                "item_types": list(set(type(item).__name__ for item in obj)),
                "sample_structure": self._analyze_json_object(obj[0], max_depth, current_depth + 1) if obj else None
            }
        else:
            return {
                "type": type(obj).__name__,
                "value": str(obj) if len(str(obj)) < 100 else str(obj)[:100] + "..."
            }
    
    def _extract_json_fields(self, data: Any, prefix: str = "") -> List[str]:
        """Extract all field paths from JSON data"""
        fields = []
        
        if isinstance(data, dict):
            for key, value in data.items():
                field_path = f"{prefix}.{key}" if prefix else key
                fields.append(field_path)
                
                if isinstance(value, (dict, list)):
                    fields.extend(self._extract_json_fields(value, field_path))
        
        elif isinstance(data, list) and data:
            # Analyze first item for structure
            if isinstance(data[0], (dict, list)):
                fields.extend(self._extract_json_fields(data[0], f"{prefix}[0]" if prefix else "[0]"))
        
        return fields
    
    def _analyze_xml_structure(self, body: str) -> Dict[str, Any]:
        """Analyze XML response structure"""
        try:
            root = ET.fromstring(body)
            
            return {
                "valid_xml": True,
                "root_tag": root.tag,
                "namespace": self._extract_xml_namespace(root.tag),
                "element_count": len(list(root.iter())),
                "structure": self._analyze_xml_element(root)
            }
            
        except ET.ParseError as e:
            return {
                "valid_xml": False,
                "error": str(e),
                "size": len(body)
            }
    
    def _analyze_xml_element(self, element: ET.Element) -> Dict[str, Any]:
        """Analyze XML element structure"""
        return {
            "tag": element.tag,
            "attributes": element.attrib,
            "text": element.text.strip() if element.text else None,
            "children": [self._analyze_xml_element(child) for child in element[:3]]  # Limit for performance
        }
    
    def _extract_xml_namespace(self, tag: str) -> Optional[str]:
        """Extract namespace from XML tag"""
        if tag.startswith('{'):
            end = tag.find('}')
            if end != -1:
                return tag[1:end]
        return None
    
    def _analyze_html_structure(self, body: str) -> Dict[str, Any]:
        """Analyze HTML response structure"""
        return {
            "type": "html",
            "size": len(body),
            "title": self._extract_html_title(body),
            "has_forms": "<form" in body.lower(),
            "has_scripts": "<script" in body.lower(),
            "has_styles": "<style" in body.lower() or "css" in body.lower(),
            "error_page": any(keyword in body.lower() for keyword in ["error", "not found", "forbidden", "unauthorized"])
        }
    
    def _extract_html_title(self, html: str) -> Optional[str]:
        """Extract title from HTML"""
        match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else None
    
    def _analyze_content(self, body: str) -> Dict[str, Any]:
        """Analyze response content"""
        analysis = {
            "length": len(body),
            "line_count": len(body.split('\n')) if body else 0,
            "word_count": len(body.split()) if body else 0,
            "contains_patterns": {},
            "data_indicators": {}
        }
        
        if not body:
            return analysis
        
        body_lower = body.lower()
        
        # Check for bank-specific patterns
        for category, patterns in self.bank_patterns.items():
            matching_patterns = [pattern for pattern in patterns if pattern in body_lower]
            if matching_patterns:
                analysis["contains_patterns"][category] = matching_patterns
        
        # Data type indicators
        analysis["data_indicators"] = {
            "has_numbers": bool(re.search(r'\d+', body)),
            "has_dates": bool(re.search(r'\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}', body)),
            "has_currencies": bool(re.search(r'[\$€£¥₹]\d+|\d+\.\d{2}', body)),
            "has_ids": bool(re.search(r'[a-zA-Z0-9]{8,}', body)),
            "has_urls": bool(re.search(r'https?://[^\s]+', body)),
            "has_emails": bool(re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', body))
        }
        
        return analysis
    
    def _analyze_errors(self, response: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze errors in the response"""
        error_analysis = {
            "has_errors": False,
            "error_types": [],
            "error_messages": [],
            "severity": "none"
        }
        
        response_lower = response.lower()
        
        # HTTP errors
        http_status = analysis.get("http_status")
        if http_status and http_status.get("category") in ["client_error", "server_error"]:
            error_analysis["has_errors"] = True
            error_analysis["error_types"].append("http_error")
            error_analysis["error_messages"].append(f"HTTP {http_status['code']}: {http_status.get('message', '')}")
            error_analysis["severity"] = "high" if http_status["category"] == "server_error" else "medium"
        
        # Content errors
        if any(indicator in response_lower for indicator in self.bank_patterns['error_indicators']):
            error_analysis["has_errors"] = True
            error_analysis["error_types"].append("content_error")
            
            # Extract error messages
            error_patterns = [
                r'error["\s]*:?["\s]*([^",\n]+)',
                r'message["\s]*:?["\s]*([^",\n]+)',
                r'description["\s]*:?["\s]*([^",\n]+)'
            ]
            
            for pattern in error_patterns:
                matches = re.findall(pattern, response, re.IGNORECASE)
                error_analysis["error_messages"].extend(matches)
        
        # Set severity if not already set
        if error_analysis["has_errors"] and error_analysis["severity"] == "none":
            error_analysis["severity"] = "medium"
        
        return error_analysis
    
    def _extract_performance_indicators(self, response: str) -> Dict[str, Any]:
        """Extract performance indicators from response"""
        indicators = {
            "response_time_indicated": False,
            "processing_time": None,
            "timestamp": None,
            "size_efficiency": "unknown"
        }
        
        # Look for timing information in headers or body
        timing_patterns = [
            r'processing[_-]?time["\s]*:?["\s]*(\d+(?:\.\d+)?)',
            r'duration["\s]*:?["\s]*(\d+(?:\.\d+)?)',
            r'elapsed["\s]*:?["\s]*(\d+(?:\.\d+)?)',
            r'x-response-time[:\s]+(\d+(?:\.\d+)?)'
        ]
        
        for pattern in timing_patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                indicators["response_time_indicated"] = True
                indicators["processing_time"] = float(match.group(1))
                break
        
        # Look for timestamps
        timestamp_patterns = [
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',
            r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'
        ]
        
        for pattern in timestamp_patterns:
            match = re.search(pattern, response)
            if match:
                indicators["timestamp"] = match.group(0)
                break
        
        # Size efficiency
        body_size = len(self._extract_body(response))
        if body_size < 1000:
            indicators["size_efficiency"] = "compact"
        elif body_size < 10000:
            indicators["size_efficiency"] = "moderate"
        else:
            indicators["size_efficiency"] = "large"
        
        return indicators
    
    def _compare_responses(self, raw_response: str, decrypted_response: str) -> Dict[str, Any]:
        """Compare raw and decrypted responses"""
        return {
            "size_difference": len(decrypted_response) - len(raw_response),
            "format_match": self._detect_response_format(raw_response) == self._detect_response_format(decrypted_response),
            "content_similarity": self._calculate_similarity(raw_response, decrypted_response),
            "decryption_successful": len(decrypted_response) > 0 and decrypted_response != raw_response,
            "structure_preserved": self._check_structure_preservation(raw_response, decrypted_response)
        }
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts (0-1)"""
        if not text1 and not text2:
            return 1.0
        if not text1 or not text2:
            return 0.0
        
        # Simple similarity based on common words
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _check_structure_preservation(self, raw: str, decrypted: str) -> bool:
        """Check if decryption preserved the structure"""
        raw_format = self._detect_response_format(raw)
        decrypted_format = self._detect_response_format(decrypted)
        
        return raw_format == decrypted_format
    
    def _assess_overall_quality(self, analysis: Dict[str, Any], bank_name: str) -> Dict[str, Any]:
        """Assess overall response quality"""
        assessment = {
            "score": 0,
            "grade": "F",
            "strengths": [],
            "weaknesses": [],
            "concerns": []
        }
        
        score = 0
        
        # Check raw response
        raw_analysis = analysis.get("raw_response_analysis", {})
        
        # Format quality (20 points)
        if raw_analysis.get("format") in ["json", "xml"]:
            score += 20
            assessment["strengths"].append("Structured response format")
        elif raw_analysis.get("format") == "html":
            score += 10
            assessment["weaknesses"].append("HTML response may indicate error page")
        else:
            assessment["weaknesses"].append("Unstructured response format")
        
        # HTTP status (30 points)
        http_status = raw_analysis.get("http_status")
        if http_status and http_status.get("success"):
            score += 30
            assessment["strengths"].append("Successful HTTP status")
        elif http_status:
            assessment["concerns"].append(f"HTTP error: {http_status.get('code')}")
        
        # Error analysis (20 points)
        error_analysis = raw_analysis.get("error_analysis", {})
        if not error_analysis.get("has_errors"):
            score += 20
            assessment["strengths"].append("No errors detected")
        else:
            severity = error_analysis.get("severity", "unknown")
            if severity == "high":
                assessment["concerns"].append("High severity errors detected")
            else:
                assessment["weaknesses"].append("Errors detected in response")
        
        # Content quality (20 points)
        content = raw_analysis.get("content_analysis", {})
        if content.get("contains_patterns", {}).get("success_indicators"):
            score += 15
            assessment["strengths"].append("Contains success indicators")
        
        if content.get("data_indicators", {}).get("has_numbers"):
            score += 5
            assessment["strengths"].append("Contains numerical data")
        
        # Encryption handling (10 points)
        if analysis.get("decrypted_response_analysis"):
            comparison = analysis.get("comparison", {})
            if comparison.get("decryption_successful"):
                score += 10
                assessment["strengths"].append("Successful response decryption")
            else:
                assessment["weaknesses"].append("Decryption issues detected")
        
        # Calculate grade
        assessment["score"] = score
        if score >= 90:
            assessment["grade"] = "A"
        elif score >= 80:
            assessment["grade"] = "B"
        elif score >= 70:
            assessment["grade"] = "C"
        elif score >= 60:
            assessment["grade"] = "D"
        else:
            assessment["grade"] = "F"
        
        return assessment
    
    def _analyze_security_aspects(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze security aspects of the response"""
        security = {
            "data_exposure": "none",
            "sensitive_data_found": [],
            "security_headers": [],
            "encryption_analysis": {},
            "recommendations": []
        }
        
        # Check for sensitive data exposure
        raw_analysis = analysis.get("raw_response_analysis", {})
        body = raw_analysis.get("body", "")
        
        for field in self.bank_patterns['sensitive_fields']:
            if field in body.lower():
                security["sensitive_data_found"].append(field)
        
        if security["sensitive_data_found"]:
            security["data_exposure"] = "high"
            security["recommendations"].append("Remove sensitive data from responses")
        
        # Check security headers
        headers = raw_analysis.get("headers", {})
        security_headers = ['x-frame-options', 'x-content-type-options', 'x-xss-protection', 'strict-transport-security']
        
        for header in security_headers:
            if header in headers:
                security["security_headers"].append(header)
        
        # Encryption analysis
        if analysis.get("decrypted_response_analysis"):
            security["encryption_analysis"] = {
                "encryption_used": True,
                "decryption_successful": analysis.get("comparison", {}).get("decryption_successful", False),
                "structure_preserved": analysis.get("comparison", {}).get("structure_preserved", False)
            }
        else:
            security["encryption_analysis"] = {
                "encryption_used": False,
                "recommendation": "Consider implementing response encryption for sensitive data"
            }
        
        return security
    
    def _generate_recommendations(self, analysis: Dict[str, Any], bank_name: str) -> List[str]:
        """Generate actionable recommendations based on analysis"""
        recommendations = []
        
        overall = analysis.get("overall_assessment", {})
        raw_analysis = analysis.get("raw_response_analysis", {})
        security = analysis.get("security_analysis", {})
        
        # Grade-based recommendations
        grade = overall.get("grade", "F")
        if grade in ["D", "F"]:
            recommendations.append("Response quality needs significant improvement")
        
        # Format recommendations
        if raw_analysis.get("format") not in ["json", "xml"]:
            recommendations.append("Use structured response format (JSON/XML) for better API integration")
        
        # Error handling recommendations
        error_analysis = raw_analysis.get("error_analysis", {})
        if error_analysis.get("has_errors") and not error_analysis.get("error_messages"):
            recommendations.append("Provide clear error messages in responses")
        
        # Security recommendations
        if security.get("data_exposure") == "high":
            recommendations.append("Implement data masking for sensitive information")
        
        if not security.get("security_headers"):
            recommendations.append("Add security headers to API responses")
        
        # Performance recommendations
        perf = raw_analysis.get("performance_indicators", {})
        if perf.get("size_efficiency") == "large":
            recommendations.append("Consider response size optimization for better performance")
        
        # Bank-specific recommendations
        if bank_name.lower() in ["hdfc", "icici", "axis"]:
            recommendations.append(f"Ensure {bank_name} API response format compliance with banking standards")
        
        # Encryption recommendations
        if not analysis.get("decrypted_response_analysis"):
            recommendations.append("Consider implementing encryption for sensitive banking data")
        
        return recommendations 