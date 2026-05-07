import os
import json
import logging
import glob
from datetime import datetime
from typing import Dict, Any, Optional

class SystemLogger:
    """
    Utility class for managing different types of logs in the SWE agent system.
    """
    
    def __init__(self, base_log_dir: str = "tmp/logs"):
        self.base_log_dir = base_log_dir
        self.agent_logs_dir = os.path.join(base_log_dir, "agent-logs")
        self.workflow_logs_dir = os.path.join(base_log_dir, "workflow-logs")
        self.system_logs_dir = os.path.join(base_log_dir, "system")
        
        # Ensure all directories exist
        self._ensure_directories()
        
        # Setup loggers
        self._setup_loggers()
    
    def _ensure_directories(self):
        """Create log directories if they don't exist."""
        for directory in [self.agent_logs_dir, self.workflow_logs_dir, self.system_logs_dir]:
            os.makedirs(directory, exist_ok=True)
    
    def _setup_loggers(self):
        """Setup different loggers for different log types."""
        # System logger
        self.system_logger = logging.getLogger('swe_agent.system')
        self.system_logger.setLevel(logging.INFO)
        
        # Tool logger
        self.tool_logger = logging.getLogger('swe_agent.tools')
        self.tool_logger.setLevel(logging.INFO)
        
        # Error logger
        self.error_logger = logging.getLogger('swe_agent.errors')
        self.error_logger.setLevel(logging.ERROR)
    
    def log_system_event(self, task_id: str, event: str, details: Dict[str, Any] = None):
        """Log a system event for a specific task."""
        try:
            log_file = os.path.join(self.system_logs_dir, f"task_{task_id}_system.log")
            timestamp = datetime.now().isoformat()
            
            log_entry = {
                "timestamp": timestamp,
                "event": event,
                "details": details or {}
            }
            
            with open(log_file, 'a') as f:
                f.write(f"[{timestamp}] {event}\n")
                if details:
                    f.write(f"Details: {json.dumps(details, indent=2)}\n")
                f.write("-" * 80 + "\n")
                
        except Exception as e:
            print(f"Error logging system event: {e}")
    
    def log_tool_usage(self, task_id: str, tool_name: str, input_data: Any, output_data: Any, duration: float = None):
        """Log tool usage for a specific task."""
        try:
            log_file = os.path.join(self.system_logs_dir, f"task_{task_id}_tools.log")
            timestamp = datetime.now().isoformat()
            
            with open(log_file, 'a') as f:
                f.write(f"[{timestamp}] Tool: {tool_name}\n")
                f.write(f"Input: {json.dumps(input_data, indent=2) if isinstance(input_data, (dict, list)) else str(input_data)}\n")
                f.write(f"Output: {json.dumps(output_data, indent=2) if isinstance(output_data, (dict, list)) else str(output_data)}\n")
                if duration:
                    f.write(f"Duration: {duration:.2f}s\n")
                f.write("-" * 80 + "\n")
                
        except Exception as e:
            print(f"Error logging tool usage: {e}")
    
    def log_error(self, task_id: str, error_type: str, error_message: str, traceback_str: str = None):
        """Log an error for a specific task."""
        try:
            log_file = os.path.join(self.system_logs_dir, f"task_{task_id}_errors.log")
            timestamp = datetime.now().isoformat()
            
            with open(log_file, 'a') as f:
                f.write(f"[{timestamp}] ERROR: {error_type}\n")
                f.write(f"Message: {error_message}\n")
                if traceback_str:
                    f.write(f"Traceback:\n{traceback_str}\n")
                f.write("-" * 80 + "\n")
                
        except Exception as e:
            print(f"Error logging error: {e}")
    
    def log_task_lifecycle(self, task_id: str, status: str, metadata: Dict[str, Any] = None):
        """Log task lifecycle events."""
        event = f"Task {status.upper()}"
        details = {
            "task_id": task_id,
            "status": status,
            "metadata": metadata or {}
        }
        self.log_system_event(task_id, event, details)
    
    def get_task_log_summary(self, task_id: str) -> Dict[str, Any]:
        """Get a summary of all logs for a specific task."""
        summary = {
            "task_id": task_id,
            "agent_logs": [],
            "workflow_logs": [],
            "system_logs": [],
            "tool_logs": [],
            "error_logs": []
        }
        
        # Check for agent logs
        agent_pattern = os.path.join(self.agent_logs_dir, f"task_{task_id}_*")
        agent_files = glob.glob(agent_pattern)
        summary["agent_logs"] = [os.path.basename(f) for f in agent_files]
        
        # Check for workflow logs
        workflow_pattern = os.path.join(self.workflow_logs_dir, f"task_{task_id}_*")
        workflow_files = glob.glob(workflow_pattern)
        summary["workflow_logs"] = [os.path.basename(f) for f in workflow_files]
        
        # Check for system logs
        system_files = [
            f"task_{task_id}_system.log",
            f"task_{task_id}_tools.log",
            f"task_{task_id}_errors.log"
        ]
        
        for log_file in system_files:
            log_path = os.path.join(self.system_logs_dir, log_file)
            if os.path.exists(log_path):
                if "system" in log_file:
                    summary["system_logs"].append(log_file)
                elif "tools" in log_file:
                    summary["tool_logs"].append(log_file)
                elif "errors" in log_file:
                    summary["error_logs"].append(log_file)
        
        return summary

# Global instance
system_logger = SystemLogger() 