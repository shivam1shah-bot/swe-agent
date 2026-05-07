"""
Process Management Utility.

This module provides centralized process management capabilities for agent tools,
including subprocess execution with worker integration, cancellation support,
and comprehensive error handling.
"""

import logging
import os
import subprocess
import time
import threading
from typing import Dict, Any, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class ProcessExecutionResult:
    """Result of a managed subprocess execution."""
    
    def __init__(self, process: subprocess.CompletedProcess, execution_time: float, 
                 worker_tracked: bool = False, task_id: Optional[str] = None):
        self.process = process
        self.execution_time = execution_time
        self.worker_tracked = worker_tracked
        self.task_id = task_id
        
    @property
    def returncode(self) -> int:
        return self.process.returncode
        
    @property
    def stdout(self) -> str:
        return self.process.stdout or ""
        
    @property
    def stderr(self) -> str:
        return self.process.stderr or ""
        
    @property
    def args(self) -> List[str]:
        return self.process.args
        
    def was_successful(self) -> bool:
        return self.process.returncode == 0


class ProcessManager:
    """
    Centralized process management for agent tools.
    
    Provides subprocess execution with worker integration, cancellation support,
    context management, and comprehensive error handling.
    """
    
    @staticmethod
    def get_current_worker_instance(task_id: Optional[str] = None):
        """Get the current worker instance from thread-local context or global state."""
        # Try to get from thread-local storage first
        current_thread = threading.current_thread()
        
        # Check if the current thread has worker_instance attribute (set by TaskProcessor)
        if hasattr(current_thread, 'worker_instance'):
            worker_instance = current_thread.worker_instance
            if worker_instance:
                logger.debug("Found worker instance from thread-local storage")
                return worker_instance
        
        # Fallback: try to get from task context registry for cross-thread access
        try:
            from src.providers.context import TaskContextRegistry
            # Use provided task_id or fallback to context lookup
            lookup_task_id = task_id or ProcessManager.get_current_task_id()
            if lookup_task_id:
                worker_instance = TaskContextRegistry.get_worker_for_task(lookup_task_id)
                if worker_instance:
                    logger.debug(f"Found worker instance from context registry for task {lookup_task_id}")
                    return worker_instance
        except Exception as e:
            logger.debug(f"Could not access task context registry: {e}")
        
        # No worker instance available - this is normal for API pods or standalone execution
        logger.debug("No worker instance available - running in API pod or standalone mode")
        return None

    @staticmethod
    def get_current_task_id() -> Optional[str]:
        """Get the current task ID from context."""
        try:
            from src.providers.context import ContextManager
            current_context = ContextManager.get_current_context()
            if current_context:
                return current_context.get('task_id')
        except:
            pass
        
        # Try thread-local storage
        current_thread = threading.current_thread()
        if hasattr(current_thread, 'task_id'):
            return current_thread.task_id
            
        return None

    @staticmethod
    def setup_execution_context(task_id: Optional[str] = None) -> Tuple[Any, str, str]:
        """Setup execution context and get worker instance.
        
        Returns:
            Tuple of (worker_instance, execution_context, process_tracking)
        """
        worker_instance = ProcessManager.get_current_worker_instance(task_id)
        execution_context = "worker pod" if worker_instance else "API pod/standalone"
        process_tracking = "enabled" if (worker_instance and task_id) else "disabled"
        
        logger.debug(f"Subprocess execution context: {execution_context}, process tracking: {process_tracking}")
        
        return worker_instance, execution_context, process_tracking

    @staticmethod
    def ensure_output_directory(output_file: str) -> None:
        """Ensure output directory exists for the given file path."""
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            logger.info(f"Created directory for output file: {output_dir}")

    @staticmethod
    def register_process_with_worker(worker_instance, task_id: str, process) -> bool:
        """Register process with worker for cancellation tracking.
        
        Returns:
            True if registration was successful, False otherwise
        """
        if not (worker_instance and task_id):
            logger.debug(f"Process {process.pid} not registered with worker (no cancellation tracking)")
            return False
            
        try:
            worker_instance.register_task_process(task_id, process.pid)
            logger.info(f"Registered process {process.pid} for task {task_id} (cancellation enabled)")
            return True
        except Exception as reg_error:
            logger.warning(f"Failed to register process {process.pid} with worker: {reg_error}")
            return False

    @staticmethod
    def unregister_process_from_worker(registration_successful: bool, worker_instance, 
                                     task_id: str, process) -> None:
        """Unregister process from worker if it was successfully registered."""
        if registration_successful and worker_instance and task_id and process:
            try:
                worker_instance.unregister_task_process(task_id, process.pid)
                logger.debug(f"Unregistered process {process.pid} for task {task_id}")
            except Exception as unreg_error:
                logger.warning(f"Failed to unregister process {process.pid} from worker: {unreg_error}")
        elif process:
            logger.debug(f"Process {process.pid} cleanup - no worker unregistration needed")

    @staticmethod
    def handle_process_error(process) -> None:
        """Handle process termination on error."""
        if process:
            try:
                if process.poll() is None:  # Process is still running
                    process.terminate()
                    process.wait(timeout=5)  # Wait up to 5 seconds for graceful termination
            except:
                pass

    @staticmethod
    def prepare_subprocess_environment(cmd: List[str], env: Dict[str, str], 
                                     additional_env: Optional[Dict[str, str]] = None,
                                     debug_flags: Optional[List[str]] = None) -> List[str]:
        """Prepare command and environment for subprocess execution.
        
        Args:
            cmd: Original command list
            env: Environment variables dictionary (modified in place)
            additional_env: Additional environment variables to add
            debug_flags: Optional debug flags to add to command
            
        Returns:
            Modified command list with any additional flags
        """
        # Add any additional environment variables
        if additional_env:
            logger.info(f"Adding {len(additional_env)} additional environment variables")
            for key, value in additional_env.items():
                env[key] = value

        # Add debug flags if configured
        if debug_flags:
            for flag in debug_flags:
                if flag not in cmd:
                    logger.info(f"Adding debug flag: {flag}")
                    cmd.insert(1, flag)  # Insert after main command

        return cmd

    @staticmethod
    def execute_with_file_output(cmd: List[str], env: Dict[str, str], output_file: str, 
                               worker_instance, task_id: str, input_text: Optional[str] = None) -> Tuple[subprocess.Popen, str, str, bool]:
        """Execute subprocess with output redirected to file.
        
        Returns:
            Tuple of (process, stdout, stderr, registration_successful)
        """
        logger.info(f"Redirecting output directly to file: {output_file}")
        ProcessManager.ensure_output_directory(output_file)

        with open(output_file, 'w') as f:
            logger.info(f"Executing subprocess.Popen with file output")
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE if input_text else None,
                stdout=f,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )
            
            registration_successful = ProcessManager.register_process_with_worker(worker_instance, task_id, process)
            stdout, stderr = process.communicate(input=input_text)
            
        return process, stdout, stderr, registration_successful

    @staticmethod
    def execute_with_captured_output(cmd: List[str], env: Dict[str, str], 
                                   worker_instance, task_id: str, 
                                   input_text: Optional[str] = None) -> Tuple[subprocess.Popen, str, str, bool]:
        """Execute subprocess with output captured in memory.
        
        Returns:
            Tuple of (process, stdout, stderr, registration_successful)
        """
        logger.info(f"Executing subprocess.Popen with captured output")
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE if input_text else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )

        registration_successful = ProcessManager.register_process_with_worker(worker_instance, task_id, process)
        stdout, stderr = process.communicate(input=input_text)
        
        return process, stdout, stderr, registration_successful

    @staticmethod
    def run_managed_subprocess(cmd: List[str], env: Dict[str, str], 
                             output_file: Optional[str] = None, 
                             task_id: Optional[str] = None,
                             tool_name: str = "unknown",
                             additional_env: Optional[Dict[str, str]] = None,
                             debug_flags: Optional[List[str]] = None,
                             input_text: Optional[str] = None) -> ProcessExecutionResult:
        """Run subprocess with comprehensive process management.
        
        Args:
            cmd: Command to execute
            env: Base environment variables
            output_file: Optional file path to write output directly to
            task_id: Optional task ID for worker tracking
            tool_name: Name of the tool executing the subprocess (for logging)
            additional_env: Additional environment variables
            debug_flags: Optional debug flags to add to command
            input_text: Optional text to send to stdin
            
        Returns:
            ProcessExecutionResult with execution details
        """
        start_time = time.time()
        
        # Prepare environment and command
        cmd = ProcessManager.prepare_subprocess_environment(cmd, env, additional_env, debug_flags)
        
        # Setup execution context
        worker_instance, execution_context, process_tracking = ProcessManager.setup_execution_context(task_id)
        
        # Log execution details
        logger.info(f"[{tool_name}] About to execute subprocess with {len(cmd)} arguments")
        logger.debug(f"[{tool_name}] Command: {' '.join(cmd)}")
        
        process = None
        registration_successful = False
        
        try:
            # Execute subprocess based on output mode
            if output_file:
                process, stdout, stderr, registration_successful = ProcessManager.execute_with_file_output(
                    cmd, env, output_file, worker_instance, task_id, input_text
                )
            else:
                process, stdout, stderr, registration_successful = ProcessManager.execute_with_captured_output(
                    cmd, env, worker_instance, task_id, input_text
                )

            # Create result object
            completed_process = subprocess.CompletedProcess(
                args=cmd,
                returncode=process.returncode,
                stdout=stdout if not output_file else '',
                stderr=stderr
            )

        except Exception as e:
            logger.exception(f"[{tool_name}] Error during subprocess execution: {e}")
            ProcessManager.handle_process_error(process)
            raise
        
        finally:
            # Cleanup process registration
            ProcessManager.unregister_process_from_worker(registration_successful, worker_instance, task_id, process)

        # Calculate execution time and log results
        execution_time = time.time() - start_time
        result = ProcessExecutionResult(
            process=completed_process,
            execution_time=execution_time,
            worker_tracked=registration_successful,
            task_id=task_id
        )
        
        logger.info(f"[{tool_name}] Command completed in {execution_time:.2f}s with return code: {result.returncode}")
        
        if result.returncode != 0:
            logger.error(f"[{tool_name}] Error output: {result.stderr}")
        else:
            if output_file:
                logger.info(f"[{tool_name}] Command succeeded, output written to: {output_file}")
            else:
                logger.info(f"[{tool_name}] Command succeeded with output length: {len(result.stdout)}")

        return result

    @staticmethod
    async def run_managed_subprocess_async(
        cmd: List[str],
        env: Dict[str, str],
        output_file: Optional[str] = None,
        task_id: Optional[str] = None,
        tool_name: str = "unknown",
        additional_env: Optional[Dict[str, str]] = None,
        debug_flags: Optional[List[str]] = None,
        input_text: Optional[str] = None,
        cwd: Optional[str] = None,
    ) -> ProcessExecutionResult:
        """
        Run subprocess asynchronously using asyncio for true parallel execution.

        This is the async version of run_managed_subprocess that uses
        asyncio.create_subprocess_exec instead of blocking subprocess.Popen.

        Args:
            cmd: Command to execute
            env: Base environment variables
            output_file: Optional file path to write output directly to
            task_id: Optional task ID for worker tracking
            tool_name: Name of the tool executing the subprocess
            additional_env: Additional environment variables
            debug_flags: Optional debug flags to add to command
            input_text: Optional text to send to stdin
            cwd: Optional working directory for subprocess execution

        Returns:
            ProcessExecutionResult with execution details
        """
        import asyncio
        start_time = time.time()

        # Prepare environment and command
        cmd = ProcessManager.prepare_subprocess_environment(
            cmd, env, additional_env, debug_flags
        )

        # Merge environment variables
        final_env = env.copy()
        if additional_env:
            final_env.update(additional_env)

        task_id = task_id or ProcessManager.get_current_task_id()

        logger.info(f"[{tool_name}] Starting async subprocess (task={task_id})")
        logger.debug(f"[{tool_name}] Command: {' '.join(cmd)}")

        output_handle = None
        try:
            # Handle output_file: redirect stdout to file if specified (matching sync version)
            if output_file:
                logger.info(f"[{tool_name}] Redirecting async output to file: {output_file}")
                ProcessManager.ensure_output_directory(output_file)
                output_handle = open(output_file, 'w')
                stdout_target = output_handle
            else:
                stdout_target = asyncio.subprocess.PIPE

            # Create async subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE if input_text else None,
                stdout=stdout_target,
                stderr=asyncio.subprocess.PIPE,
                env=final_env,
                cwd=cwd,
            )

            # Register PID with worker so cancellation can terminate the process
            worker_instance = ProcessManager.get_current_worker_instance(task_id)
            registration_successful = ProcessManager.register_process_with_worker(
                worker_instance, task_id, process
            )

            try:
                # Communicate with subprocess (non-blocking in async context)
                stdout_bytes, stderr_bytes = await process.communicate(
                    input=input_text.encode() if input_text else None
                )
            finally:
                ProcessManager.unregister_process_from_worker(
                    registration_successful, worker_instance, task_id, process
                )

            # Close output file handle if used
            if output_handle:
                output_handle.close()
                output_handle = None

            # stdout is empty if written to file (matching sync version behavior)
            stdout = "" if output_file else (stdout_bytes.decode() if stdout_bytes else "")
            stderr = stderr_bytes.decode() if stderr_bytes else ""

            # Create completed process object
            completed_process = subprocess.CompletedProcess(
                args=cmd,
                returncode=process.returncode,
                stdout=stdout,
                stderr=stderr,
            )

            execution_time = time.time() - start_time

            result = ProcessExecutionResult(
                process=completed_process,
                execution_time=execution_time,
                worker_tracked=registration_successful,
                task_id=task_id,
            )

            logger.info(
                f"[{tool_name}] Async command completed in {execution_time:.2f}s "
                f"with return code: {result.returncode}"
            )

            if result.returncode != 0:
                logger.error(f"[{tool_name}] Error output: {result.stderr}")
            else:
                if output_file:
                    logger.info(f"[{tool_name}] Command succeeded, output written to: {output_file}")
                else:
                    logger.info(f"[{tool_name}] Command succeeded with output length: {len(result.stdout)}")

            return result

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"[{tool_name}] Async command failed after {execution_time:.2f}s: {e}"
            )
            raise
        finally:
            # Ensure output file handle is closed on error
            if output_handle:
                try:
                    output_handle.close()
                except Exception:
                    pass

    @staticmethod
    def run_simple_subprocess(cmd: List[str], env: Optional[Dict[str, str]] = None,
                            output_file: Optional[str] = None,
                            input_text: Optional[str] = None,
                            tool_name: str = "unknown") -> ProcessExecutionResult:
        """Run subprocess without worker integration (simplified version).
        
        Args:
            cmd: Command to execute
            env: Environment variables (uses os.environ if not provided)
            output_file: Optional file path to write output directly to
            input_text: Optional text to send to stdin
            tool_name: Name of the tool executing the subprocess (for logging)
            
        Returns:
            ProcessExecutionResult with execution details
        """
        if env is None:
            env = os.environ.copy()
            
        start_time = time.time()
        
        logger.info(f"[{tool_name}] About to execute subprocess with {len(cmd)} arguments")
        logger.debug(f"[{tool_name}] Command: {' '.join(cmd)}")

        try:
            # If output_file is provided, redirect output directly to the file
            if output_file:
                logger.info(f"[{tool_name}] Redirecting output directly to file: {output_file}")
                ProcessManager.ensure_output_directory(output_file)

                # Execute command with output redirected to file
                with open(output_file, 'w') as f:
                    completed_process = subprocess.run(
                        cmd,
                        input=input_text,
                        stdout=f,
                        stderr=subprocess.PIPE,
                        text=True,
                        env=env
                    )
            else:
                # Execute command and capture output in memory
                logger.info(f"[{tool_name}] Executing subprocess with captured output")
                completed_process = subprocess.run(
                    cmd,
                    input=input_text,
                    capture_output=True,
                    text=True,
                    env=env
                )

        except Exception as e:
            logger.exception(f"[{tool_name}] Error during subprocess execution: {e}")
            raise

        # Calculate execution time and create result
        execution_time = time.time() - start_time
        result = ProcessExecutionResult(
            process=completed_process,
            execution_time=execution_time,
            worker_tracked=False,
            task_id=None
        )

        logger.info(f"[{tool_name}] Command completed in {execution_time:.2f}s with return code: {result.returncode}")
        
        if result.returncode != 0:
            logger.error(f"[{tool_name}] Error output: {result.stderr}")
        else:
            if output_file:
                logger.info(f"[{tool_name}] Command succeeded, output written to: {output_file}")
            else:
                logger.info(f"[{tool_name}] Command succeeded with output length: {len(result.stdout)}")

        return result
