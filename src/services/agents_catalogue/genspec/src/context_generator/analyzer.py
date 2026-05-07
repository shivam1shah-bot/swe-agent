"""
Code analyzer module for Context Generator.

This module provides functionality to analyze a codebase and extract insights
about its structure, flow, API requirements, and potential failure points.
"""

import os
import re
import ast
import json
from typing import Dict, List, Any, Optional, Set, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class CodebaseAnalyzer:
    """
    Analyzes a codebase to extract insights about structure, flow, APIs, and failure points.
    """
    
    def __init__(self, codebase_path: str, ignore_patterns: List[str] = None):
        """
        Initialize the codebase analyzer.
        
        Args:
            codebase_path: Path to the codebase to analyze
            ignore_patterns: List of glob patterns to ignore (e.g., '*.pyc', '__pycache__', etc.)
        """
        self.codebase_path = os.path.abspath(codebase_path)
        self.ignore_patterns = ignore_patterns or [
            '*.pyc', '__pycache__', '*.git*', '*.idea*', '*.vscode*',
            'node_modules', 'venv', 'env', '.env', '*.egg-info',
            'dist', 'build', '*.log', '*.tmp', '*.bak', '*.swp'
        ]
        
        # Analysis results
        self.structure = {}
        self.flows = []
        self.apis = []
        self.jobs = []
        self.external_calls = []
        self.db_operations = []
        self.failure_points = []
        self.retry_mechanisms = []
        self.idempotency_mechanisms = []
    
    def analyze(self) -> Dict[str, Any]:
        """
        Analyze the codebase and extract insights.
        
        Returns:
            Dict containing analysis results.
        """
        logger.info(f"Analyzing codebase at: {self.codebase_path}")
        
        # Analyze project structure
        self._analyze_structure()
        
        # Analyze Python files
        self._analyze_python_files()
        
        # Identify APIs and jobs
        self._identify_apis_and_jobs()
        
        # Identify external calls and failure points
        self._identify_external_calls()
        
        # Identify database operations
        self._identify_db_operations()
        
        # Identify retry and idempotency mechanisms
        self._identify_retry_mechanisms()
        self._identify_idempotency_mechanisms()
        
        # Return analysis results
        return {
            "structure": self.structure,
            "flows": self.flows,
            "apis": self.apis,
            "jobs": self.jobs,
            "external_calls": self.external_calls,
            "db_operations": self.db_operations,
            "failure_points": self.failure_points,
            "retry_mechanisms": self.retry_mechanisms,
            "idempotency_mechanisms": self.idempotency_mechanisms
        }
    
    def _analyze_structure(self) -> None:
        """
        Analyze the project structure and build a tree representation.
        """
        logger.info("Analyzing project structure")
        
        def should_ignore(path: str) -> bool:
            """Check if a path should be ignored based on ignore patterns."""
            import fnmatch
            path_obj = Path(path)
            for pattern in self.ignore_patterns:
                if fnmatch.fnmatch(path_obj.name, pattern):
                    return True
            return False
        
        def build_tree(path: str, rel_path: str = "") -> Dict[str, Any]:
            """Build a tree representation of the directory structure."""
            if should_ignore(path):
                return None
            
            if os.path.isfile(path):
                return {
                    "type": "file",
                    "name": os.path.basename(path),
                    "path": rel_path,
                    "size": os.path.getsize(path)
                }
            
            result = {
                "type": "directory",
                "name": os.path.basename(path) or path,
                "path": rel_path,
                "children": []
            }
            
            try:
                for item in os.listdir(path):
                    item_path = os.path.join(path, item)
                    item_rel_path = os.path.join(rel_path, item)
                    child = build_tree(item_path, item_rel_path)
                    if child:
                        result["children"].append(child)
            except PermissionError:
                logger.warning(f"Permission denied: {path}")
            
            return result
        
        self.structure = build_tree(self.codebase_path)
    
    def _analyze_python_files(self) -> None:
        """
        Analyze Python files in the codebase to extract insights.
        """
        logger.info("Analyzing Python files")
        
        python_files = self._find_files_by_extension(".py")
        
        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Parse the Python file
                tree = ast.parse(content)
                
                # Extract functions, classes, and imports
                functions = []
                classes = []
                imports = []
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        functions.append({
                            "name": node.name,
                            "line": node.lineno,
                            "args": [arg.arg for arg in node.args.args],
                            "decorators": [self._get_decorator_name(d) for d in node.decorator_list]
                        })
                    elif isinstance(node, ast.ClassDef):
                        classes.append({
                            "name": node.name,
                            "line": node.lineno,
                            "bases": [self._get_name(base) for base in node.bases],
                            "decorators": [self._get_decorator_name(d) for d in node.decorator_list]
                        })
                    elif isinstance(node, ast.Import):
                        for name in node.names:
                            imports.append({
                                "name": name.name,
                                "alias": name.asname
                            })
                    elif isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                        for name in node.names:
                            imports.append({
                                "name": f"{module}.{name.name}" if module else name.name,
                                "alias": name.asname,
                                "from_import": True,
                                "module": module
                            })
                
                # Add to flows if it looks like a flow definition
                rel_path = os.path.relpath(file_path, self.codebase_path)
                if any(kw in rel_path.lower() for kw in ["flow", "process", "workflow", "pipeline"]):
                    self.flows.append({
                        "path": rel_path,
                        "functions": functions,
                        "classes": classes,
                        "imports": imports
                    })
                
                # Check for API endpoints
                self._check_for_api_endpoints(file_path, rel_path, functions, classes, content)
                
                # Check for job definitions
                self._check_for_job_definitions(file_path, rel_path, functions, classes, content)
                
                # Check for external calls
                self._check_for_external_calls(file_path, rel_path, content)
                
                # Check for database operations
                self._check_for_db_operations(file_path, rel_path, content)
                
            except Exception as e:
                logger.error(f"Error analyzing file {file_path}: {str(e)}")
    
    def _find_files_by_extension(self, extension: str) -> List[str]:
        """
        Find all files with the given extension in the codebase.
        
        Args:
            extension: File extension to search for (e.g., '.py')
            
        Returns:
            List of file paths
        """
        result = []
        
        for root, _, files in os.walk(self.codebase_path):
            # Check if directory should be ignored
            if any(pattern in root for pattern in self.ignore_patterns):
                continue
                
            for file in files:
                if file.endswith(extension):
                    file_path = os.path.join(root, file)
                    result.append(file_path)
        
        return result
    
    def _get_name(self, node) -> str:
        """Extract name from an AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        else:
            return "unknown"
    
    def _get_decorator_name(self, node) -> str:
        """Extract decorator name from an AST node."""
        if isinstance(node, ast.Call):
            return self._get_name(node.func)
        else:
            return self._get_name(node)
    
    def _check_for_api_endpoints(self, file_path: str, rel_path: str, 
                                functions: List[Dict[str, Any]], 
                                classes: List[Dict[str, Any]], 
                                content: str) -> None:
        """
        Check for API endpoint definitions in the file.
        
        Args:
            file_path: Absolute path to the file
            rel_path: Relative path from the codebase root
            functions: List of functions in the file
            classes: List of classes in the file
            content: File content
        """
        # Common API framework patterns
        api_patterns = [
            # Flask
            r'@(?:app|blueprint)\.(?:route|get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)[\'"]',
            # FastAPI
            r'@(?:app|router)\.(?:get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)[\'"]',
            # Django
            r'path\s*\(\s*[\'"]([^\'"]+)[\'"]',
            # Generic API endpoint indicators
            r'class\s+\w+(?:API|View|Controller|Resource|Endpoint)',
            r'def\s+\w+_api\s*\(',
            r'def\s+api_\w+\s*\(',
        ]
        
        for pattern in api_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                endpoint_path = match.group(1) if match.lastindex else "unknown"
                
                # Get the function or class associated with this endpoint
                line_num = content[:match.start()].count('\n') + 1
                associated_function = next((f for f in functions if f["line"] > line_num), None)
                associated_class = next((c for c in classes if c["line"] > line_num), None)
                
                endpoint_info = {
                    "path": endpoint_path,
                    "file": rel_path,
                    "line": line_num,
                    "type": self._determine_endpoint_type(match.group(0)),
                    "function": associated_function["name"] if associated_function else None,
                    "class": associated_class["name"] if associated_class else None
                }
                
                self.apis.append(endpoint_info)
    
    def _determine_endpoint_type(self, match_text: str) -> str:
        """Determine the HTTP method type from the matched text."""
        if ".get" in match_text.lower():
            return "GET"
        elif ".post" in match_text.lower():
            return "POST"
        elif ".put" in match_text.lower():
            return "PUT"
        elif ".delete" in match_text.lower():
            return "DELETE"
        elif ".patch" in match_text.lower():
            return "PATCH"
        else:
            return "UNKNOWN"
    
    def _check_for_job_definitions(self, file_path: str, rel_path: str, 
                                  functions: List[Dict[str, Any]], 
                                  classes: List[Dict[str, Any]], 
                                  content: str) -> None:
        """
        Check for job/task definitions in the file.
        
        Args:
            file_path: Absolute path to the file
            rel_path: Relative path from the codebase root
            functions: List of functions in the file
            classes: List of classes in the file
            content: File content
        """
        # Common job/task framework patterns
        job_patterns = [
            # Celery
            r'@(?:celery|app)\.task',
            # Airflow
            r'PythonOperator\(',
            r'DAG\(',
            # Generic job/task indicators
            r'class\s+\w+(?:Job|Task|Worker|Scheduler)',
            r'def\s+\w+_job\s*\(',
            r'def\s+job_\w+\s*\(',
            r'def\s+\w+_task\s*\(',
            r'def\s+task_\w+\s*\(',
            r'@scheduled',
            r'@cron',
            r'@periodic',
        ]
        
        for pattern in job_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                # Get the function or class associated with this job
                line_num = content[:match.start()].count('\n') + 1
                associated_function = next((f for f in functions if f["line"] > line_num), None)
                associated_class = next((c for c in classes if c["line"] > line_num), None)
                
                job_info = {
                    "file": rel_path,
                    "line": line_num,
                    "type": self._determine_job_type(match.group(0)),
                    "function": associated_function["name"] if associated_function else None,
                    "class": associated_class["name"] if associated_class else None
                }
                
                # Try to extract schedule information
                schedule_match = re.search(r'schedule\s*=\s*[\'"]([^\'"]+)[\'"]', 
                                          content[match.start():match.start() + 500])
                if schedule_match:
                    job_info["schedule"] = schedule_match.group(1)
                
                self.jobs.append(job_info)
    
    def _determine_job_type(self, match_text: str) -> str:
        """Determine the job type from the matched text."""
        if "celery" in match_text.lower() or "task" in match_text.lower():
            return "CELERY_TASK"
        elif "dag" in match_text.lower() or "airflow" in match_text.lower():
            return "AIRFLOW_DAG"
        elif "cron" in match_text.lower():
            return "CRON_JOB"
        elif "scheduled" in match_text.lower() or "periodic" in match_text.lower():
            return "SCHEDULED_TASK"
        else:
            return "UNKNOWN_JOB"
    
    def _check_for_external_calls(self, file_path: str, rel_path: str, content: str) -> None:
        """
        Check for external service calls in the file.
        
        Args:
            file_path: Absolute path to the file
            rel_path: Relative path from the codebase root
            content: File content
        """
        # Common patterns for external service calls
        external_call_patterns = [
            # HTTP requests
            r'requests\.(?:get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)[\'"]',
            r'urllib\.request\.urlopen\s*\(\s*[\'"]([^\'"]+)[\'"]',
            r'http\.client\.HTTPConnection\s*\(\s*[\'"]([^\'"]+)[\'"]',
            # API clients
            r'client\.(?:get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)[\'"]',
            r'api\.(?:get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)[\'"]',
            # AWS services
            r'boto3\.client\s*\(\s*[\'"]([^\'"]+)[\'"]',
            r'boto3\.resource\s*\(\s*[\'"]([^\'"]+)[\'"]',
            # Generic external service indicators
            r'(?:service|client)\.call\s*\(\s*[\'"]([^\'"]+)[\'"]',
        ]
        
        for pattern in external_call_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                service_name = match.group(1) if match.lastindex else "unknown"
                line_num = content[:match.start()].count('\n') + 1
                
                # Check for retry mechanisms around this call
                retry_pattern = r'(?:retry|backoff|attempt|try_again)'
                has_retry = bool(re.search(retry_pattern, content[max(0, match.start() - 200):match.end() + 200]))
                
                # Check for error handling around this call
                error_handling_pattern = r'(?:try|except|catch|finally|raise|error|exception)'
                has_error_handling = bool(re.search(error_handling_pattern, 
                                                   content[max(0, match.start() - 200):match.end() + 200]))
                
                external_call_info = {
                    "service": service_name,
                    "file": rel_path,
                    "line": line_num,
                    "type": self._determine_external_call_type(match.group(0)),
                    "has_retry": has_retry,
                    "has_error_handling": has_error_handling,
                    "is_failure_point": True  # External calls are potential failure points
                }
                
                self.external_calls.append(external_call_info)
                
                # Add to failure points if it doesn't have proper error handling
                if not has_error_handling or not has_retry:
                    self.failure_points.append({
                        "type": "EXTERNAL_CALL",
                        "file": rel_path,
                        "line": line_num,
                        "description": f"External call to {service_name} without {'retry mechanism' if not has_retry else 'error handling'}",
                        "recommendation": f"Implement {'retry logic' if not has_retry else 'error handling'} for this external call"
                    })
    
    def _determine_external_call_type(self, match_text: str) -> str:
        """Determine the external call type from the matched text."""
        if "requests." in match_text.lower():
            return "HTTP_REQUEST"
        elif "urllib" in match_text.lower():
            return "URLLIB_REQUEST"
        elif "boto3" in match_text.lower():
            return "AWS_SERVICE"
        elif "client" in match_text.lower():
            return "API_CLIENT"
        else:
            return "UNKNOWN_EXTERNAL_CALL"
    
    def _check_for_db_operations(self, file_path: str, rel_path: str, content: str) -> None:
        """
        Check for database operations in the file.
        
        Args:
            file_path: Absolute path to the file
            rel_path: Relative path from the codebase root
            content: File content
        """
        # Common patterns for database operations
        db_patterns = [
            # SQL Alchemy
            r'(?:session|db)\.(?:query|add|delete|commit|execute|update)',
            # Django ORM
            r'\.objects\.(?:create|get|filter|update|delete|all)',
            # Raw SQL
            r'cursor\.execute\s*\(\s*[\'"]([^\'"]+)[\'"]',
            r'execute\s*\(\s*[\'"]([^\'"]+)[\'"]',
            # MongoDB
            r'(?:collection|db)\.(?:find|insert|update|delete|aggregate)',
            # Generic database indicators
            r'(?:INSERT|UPDATE|DELETE|SELECT)\s+(?:INTO|FROM)',
        ]
        
        for pattern in db_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                operation_text = match.group(0)
                line_num = content[:match.start()].count('\n') + 1
                
                # Check for transaction handling
                transaction_pattern = r'(?:transaction|atomic|commit|rollback|session)'
                has_transaction = bool(re.search(transaction_pattern, 
                                               content[max(0, match.start() - 200):match.end() + 200]))
                
                # Check for error handling
                error_handling_pattern = r'(?:try|except|catch|finally|raise|error|exception)'
                has_error_handling = bool(re.search(error_handling_pattern, 
                                                  content[max(0, match.start() - 200):match.end() + 200]))
                
                # Check for idempotency keys or mechanisms
                idempotency_pattern = r'(?:idempotent|idempotency|upsert|ON\s+CONFLICT|IF\s+NOT\s+EXISTS)'
                has_idempotency = bool(re.search(idempotency_pattern, 
                                               content[max(0, match.start() - 200):match.end() + 200]))
                
                db_operation_info = {
                    "operation": operation_text,
                    "file": rel_path,
                    "line": line_num,
                    "type": self._determine_db_operation_type(operation_text),
                    "has_transaction": has_transaction,
                    "has_error_handling": has_error_handling,
                    "has_idempotency": has_idempotency,
                    "is_failure_point": True  # Database operations are potential failure points
                }
                
                self.db_operations.append(db_operation_info)
                
                # Add to failure points if it doesn't have proper error handling or transaction
                if not has_error_handling or not has_transaction:
                    self.failure_points.append({
                        "type": "DB_OPERATION",
                        "file": rel_path,
                        "line": line_num,
                        "description": f"Database operation without {'transaction handling' if not has_transaction else 'error handling'}",
                        "recommendation": f"Implement {'transaction handling' if not has_transaction else 'error handling'} for this database operation"
                    })
                
                # Add to idempotency concerns if it's a write operation without idempotency
                if not has_idempotency and any(op in operation_text.lower() for op in ["insert", "update", "delete", "add", "create"]):
                    self.failure_points.append({
                        "type": "IDEMPOTENCY_CONCERN",
                        "file": rel_path,
                        "line": line_num,
                        "description": "Database write operation without idempotency mechanism",
                        "recommendation": "Implement idempotency checks for this operation to prevent duplicates"
                    })
    
    def _determine_db_operation_type(self, match_text: str) -> str:
        """Determine the database operation type from the matched text."""
        match_text_lower = match_text.lower()
        if "select" in match_text_lower or "query" in match_text_lower or "get" in match_text_lower or "find" in match_text_lower:
            return "READ"
        elif "insert" in match_text_lower or "create" in match_text_lower or "add" in match_text_lower:
            return "CREATE"
        elif "update" in match_text_lower:
            return "UPDATE"
        elif "delete" in match_text_lower:
            return "DELETE"
        else:
            return "UNKNOWN_DB_OPERATION"
    
    def _identify_apis_and_jobs(self) -> None:
        """
        Further analyze APIs and jobs to extract additional information.
        """
        # This method can be expanded to extract more details about APIs and jobs
        # For now, we'll just log the count
        logger.info(f"Identified {len(self.apis)} API endpoints and {len(self.jobs)} jobs")
    
    def _identify_external_calls(self) -> None:
        """
        Further analyze external calls to identify failure points.
        """
        # This method can be expanded to extract more details about external calls
        # For now, we'll just log the count
        logger.info(f"Identified {len(self.external_calls)} external calls")
    
    def _identify_db_operations(self) -> None:
        """
        Further analyze database operations to identify failure points.
        """
        # This method can be expanded to extract more details about database operations
        # For now, we'll just log the count
        logger.info(f"Identified {len(self.db_operations)} database operations")
    
    def _identify_retry_mechanisms(self) -> None:
        """
        Identify retry mechanisms in the codebase.
        """
        python_files = self._find_files_by_extension(".py")
        
        retry_patterns = [
            r'def\s+retry',
            r'@retry',
            r'retry\s*\(',
            r'retries\s*=',
            r'max_retries',
            r'backoff',
            r'for\s+attempt\s+in\s+range',
            r'while\s+attempts',
        ]
        
        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                rel_path = os.path.relpath(file_path, self.codebase_path)
                
                for pattern in retry_patterns:
                    matches = re.finditer(pattern, content)
                    for match in matches:
                        line_num = content[:match.start()].count('\n') + 1
                        
                        # Extract surrounding context
                        start_pos = max(0, match.start() - 200)
                        end_pos = min(len(content), match.end() + 200)
                        context = content[start_pos:end_pos]
                        
                        retry_info = {
                            "file": rel_path,
                            "line": line_num,
                            "pattern": match.group(0),
                            "context": context
                        }
                        
                        self.retry_mechanisms.append(retry_info)
            
            except Exception as e:
                logger.error(f"Error analyzing file {file_path} for retry mechanisms: {str(e)}")
    
    def _identify_idempotency_mechanisms(self) -> None:
        """
        Identify idempotency mechanisms in the codebase.
        """
        python_files = self._find_files_by_extension(".py")
        
        idempotency_patterns = [
            r'idempotent',
            r'idempotency',
            r'idempotency_key',
            r'upsert',
            r'ON\s+CONFLICT',
            r'IF\s+NOT\s+EXISTS',
            r'already_exists',
            r'duplicate',
        ]
        
        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                rel_path = os.path.relpath(file_path, self.codebase_path)
                
                for pattern in idempotency_patterns:
                    matches = re.finditer(pattern, content)
                    for match in matches:
                        line_num = content[:match.start()].count('\n') + 1
                        
                        # Extract surrounding context
                        start_pos = max(0, match.start() - 200)
                        end_pos = min(len(content), match.end() + 200)
                        context = content[start_pos:end_pos]
                        
                        idempotency_info = {
                            "file": rel_path,
                            "line": line_num,
                            "pattern": match.group(0),
                            "context": context
                        }
                        
                        self.idempotency_mechanisms.append(idempotency_info)
            
            except Exception as e:
                logger.error(f"Error analyzing file {file_path} for idempotency mechanisms: {str(e)}") 