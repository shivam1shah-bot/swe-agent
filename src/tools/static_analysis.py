"""
Static Analysis Tool module.
This module provides tools for static code analysis.
"""

import logging
import subprocess
import json
import tempfile
import os
from typing import Dict, Any, List, Optional

from .base import BaseTool

logger = logging.getLogger(__name__)

class LintingTool(BaseTool):
    """
    Tool for performing static code analysis using linters.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the Linting Tool.
        
        Args:
            config: Configuration for the tool
        """
        super().__init__(
            name="linting",
            description="Performs static code analysis using various linters",
            config=config
        )
        
        # Configure available linters
        self.linters = {
            "pylint": self._run_pylint,
            "golangci-lint": self._run_golangci_lint,
            "eslint": self._run_eslint
        }
        
        logger.info("Linting Tool initialized")
    
    async def execute(self, params: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute the linting tool.
        
        Args:
            params: Parameters for the tool execution
                - linter: The linter to use (pylint, golangci-lint, eslint)
                - code: The code to analyze (string)
                - file_path: Path to the file to analyze (alternative to code)
                - options: Additional options for the linter
            context: Additional context
            
        Returns:
            Dict[str, Any]: The linting results
        """
        if not self.validate_params(params):
            return {"error": "Invalid parameters"}
        
        linter = params.get("linter", "pylint")
        code = params.get("code")
        file_path = params.get("file_path")
        options = params.get("options", {})
        
        # Check if the requested linter is available
        if linter not in self.linters:
            return {
                "error": f"Unsupported linter: {linter}",
                "available_linters": list(self.linters.keys())
            }
        
        try:
            # Run the appropriate linter
            linter_func = self.linters[linter]
            result = await linter_func(code, file_path, options)
            
            return {
                "linter": linter,
                "success": True,
                "results": result
            }
        
        except Exception as e:
            logger.exception(f"Error running linter {linter}: {e}")
            return {
                "linter": linter,
                "success": False,
                "error": str(e)
            }
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """
        Validate the parameters for the tool.
        
        Args:
            params: Parameters to validate
            
        Returns:
            bool: True if parameters are valid, False otherwise
        """
        # Either code or file_path must be provided
        if "code" not in params and "file_path" not in params:
            logger.error("Either code or file_path must be provided")
            return False
        
        return True
    
    async def _run_pylint(self, code: Optional[str], file_path: Optional[str], options: Dict[str, Any]) -> Dict[str, Any]:
        """Run pylint on the provided code or file."""
        temp_file = None
        
        try:
            if code:
                # Create a temporary file for the code
                fd, temp_file = tempfile.mkstemp(suffix=".py")
                with os.fdopen(fd, 'w') as f:
                    f.write(code)
                target = temp_file
            else:
                target = file_path
            
            # Build pylint command
            cmd = ["pylint", "--output-format=json"]
            
            # Add any additional options
            for key, value in options.items():
                if isinstance(value, bool) and value:
                    cmd.append(f"--{key}")
                elif not isinstance(value, bool):
                    cmd.append(f"--{key}={value}")
            
            # Add the target file
            cmd.append(target)
            
            # Run pylint
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Parse the output
            if result.stdout:
                try:
                    issues = json.loads(result.stdout)
                    return {
                        "issues": issues,
                        "count": len(issues)
                    }
                except json.JSONDecodeError:
                    return {
                        "raw_output": result.stdout,
                        "error_parsing": True
                    }
            else:
                return {
                    "issues": [],
                    "count": 0,
                    "stderr": result.stderr
                }
        
        finally:
            # Clean up temporary file if created
            if temp_file and os.path.exists(temp_file):
                os.unlink(temp_file)
    
    async def _run_golangci_lint(self, code: Optional[str], file_path: Optional[str], options: Dict[str, Any]) -> Dict[str, Any]:
        """Run golangci-lint on the provided code or file."""
        temp_dir = None
        
        try:
            if code:
                # Create a temporary directory for the code
                temp_dir = tempfile.mkdtemp()
                file_name = options.get("file_name", "main.go")
                target_file = os.path.join(temp_dir, file_name)
                
                with open(target_file, 'w') as f:
                    f.write(code)
                
                target_dir = temp_dir
            else:
                # Get the directory containing the file
                target_dir = os.path.dirname(file_path)
            
            # Build golangci-lint command
            cmd = ["golangci-lint", "run", "--out-format=json"]
            
            # Add any additional options
            for key, value in options.items():
                if key == "file_name":
                    continue
                
                if isinstance(value, bool) and value:
                    cmd.append(f"--{key}")
                elif not isinstance(value, bool):
                    cmd.append(f"--{key}={value}")
            
            # Add the target directory
            cmd.append(target_dir)
            
            # Run golangci-lint
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Parse the output
            if result.stdout:
                try:
                    data = json.loads(result.stdout)
                    return {
                        "issues": data.get("Issues", []),
                        "count": len(data.get("Issues", [])),
                        "linters": data.get("Linters", [])
                    }
                except json.JSONDecodeError:
                    return {
                        "raw_output": result.stdout,
                        "error_parsing": True
                    }
            else:
                return {
                    "issues": [],
                    "count": 0,
                    "stderr": result.stderr
                }
        
        finally:
            # Clean up temporary directory if created
            if temp_dir and os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir)
    
    async def _run_eslint(self, code: Optional[str], file_path: Optional[str], options: Dict[str, Any]) -> Dict[str, Any]:
        """Run eslint on the provided code or file."""
        temp_file = None
        
        try:
            if code:
                # Create a temporary file for the code
                fd, temp_file = tempfile.mkstemp(suffix=".js")
                with os.fdopen(fd, 'w') as f:
                    f.write(code)
                target = temp_file
            else:
                target = file_path
            
            # Build eslint command
            cmd = ["eslint", "--format=json"]
            
            # Add any additional options
            for key, value in options.items():
                if isinstance(value, bool) and value:
                    cmd.append(f"--{key}")
                elif not isinstance(value, bool):
                    cmd.append(f"--{key}={value}")
            
            # Add the target file
            cmd.append(target)
            
            # Run eslint
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Parse the output
            if result.stdout:
                try:
                    issues = json.loads(result.stdout)
                    return {
                        "issues": issues,
                        "count": sum(len(file_issues.get("messages", [])) for file_issues in issues)
                    }
                except json.JSONDecodeError:
                    return {
                        "raw_output": result.stdout,
                        "error_parsing": True
                    }
            else:
                return {
                    "issues": [],
                    "count": 0,
                    "stderr": result.stderr
                }
        
        finally:
            # Clean up temporary file if created
            if temp_file and os.path.exists(temp_file):
                os.unlink(temp_file)
    
    def _get_parameter_schema(self) -> Dict[str, Any]:
        """Get the parameter schema for this tool."""
        return {
            "type": "object",
            "properties": {
                "linter": {
                    "type": "string",
                    "enum": list(self.linters.keys()),
                    "description": "The linter to use"
                },
                "code": {
                    "type": "string",
                    "description": "The code to analyze"
                },
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to analyze (alternative to code)"
                },
                "options": {
                    "type": "object",
                    "description": "Additional options for the linter"
                }
            },
            "oneOf": [
                {"required": ["code"]},
                {"required": ["file_path"]}
            ]
        }
    
    def _get_output_schema(self) -> Dict[str, Any]:
        """Get the output schema for this tool."""
        return {
            "type": "object",
            "properties": {
                "linter": {
                    "type": "string",
                    "description": "The linter that was used"
                },
                "success": {
                    "type": "boolean",
                    "description": "Whether the linting was successful"
                },
                "results": {
                    "type": "object",
                    "description": "The linting results"
                },
                "error": {
                    "type": "string",
                    "description": "Error message if the linting failed"
                }
            }
        }
