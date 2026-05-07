"""
SWE Agent Worker - Main worker process that listens to queues and processes tasks.
"""

import logging
import os
import signal
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Optional, List
from pathlib import Path

# Add the project root to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from .queue_manager import QueueManager
from .tasks import TaskProcessor
from src.providers.config_loader import get_config
from src.tasks.service import task_manager
from src.constants.github_bots import GitHubBot, DEFAULT_BOT
# GitHub auth is now handled via tasks and simplified auth service

logger = logging.getLogger(__name__)


class SWEAgentWorker:
    """
    Main worker class that processes SWE Agent tasks from queues.
    Supports graceful shutdown and configurable concurrency.
    """
    
    def __init__(self, worker_id: Optional[str] = None, max_tasks_per_run: int = 1):
        """
        Initialize the SWE Agent Worker.
        
        Args:
            worker_id: Unique identifier for this worker instance
            max_tasks_per_run: Maximum number of tasks to process in one polling cycle
        """
        self.worker_id = worker_id or f"worker-{int(time.time())}"
        self.max_tasks_per_run = max_tasks_per_run
        self.env_name = os.getenv("APP_ENV", "dev")
        self.config = get_config()

        # GitHub bot this worker handles (subclasses may set this before calling super().__init__)
        if not hasattr(self, 'github_bot'):
            self.github_bot: GitHubBot = DEFAULT_BOT

        # Initialize components
        self.queue_manager = QueueManager()
        self.task_processor = TaskProcessor()
        
        # Pass worker reference to task processor for cancellation checks
        self.task_processor.set_worker_instance(self)
        
        # Initialize GitHub authentication (simplified for worker)
        self._setup_github_auth()

        # Write Google Workspace CLI credentials so `gws` can authenticate
        self._setup_gws_credentials()

        # Initialize telemetry/metrics
        self._setup_telemetry()
        
        # Worker state
        self.is_running = False
        self.should_stop = threading.Event()
        
        # Running task registry for cancellation monitoring
        self.running_tasks = {}  # {task_id: {start_time, task_data, cancel_requested}}
        self.task_lock = threading.Lock()

        # Statistics lock for thread-safe counter updates
        self.stats_lock = threading.Lock()

        # Task type filtering - None means accept all types
        self.accepted_task_types: Optional[List[str]] = None

        # Load accepted task types from worker profile config
        self._load_accepted_task_types_from_config()

        # Statistics
        self.tasks_processed = 0
        self.tasks_failed = 0
        self.start_time = None
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()
        
        # Initialize GitHub CLI sync service
        self._setup_cli_sync_service()
        
        # Initialize background cancellation monitor
        self._setup_cancellation_monitor()
        
        logger.info(f"SWEAgentWorker {self.worker_id} initialized in {self.env_name} environment")

    def _get_worker_profile_name(self) -> str:
        """
        Get the worker profile name for loading config.
        Override in subclasses to specify a different profile.

        Returns:
            str: Profile name (e.g., 'task_execution', 'code_review')
        """
        return "task_execution"  # Default profile

    def _load_accepted_task_types_from_config(self):
        """Load accepted task types from worker profile configuration."""
        profile_name = self._get_worker_profile_name()
        profiles = self.config.get('worker', {}).get('profiles', {})
        profile_config = profiles.get(profile_name, {})

        accepted_types = profile_config.get('accepted_task_types')
        if accepted_types:
            self.accepted_task_types = accepted_types
            logger.debug(f"Worker {self.worker_id} loaded accepted task types from profile '{profile_name}': {accepted_types}")
        else:
            logger.debug(f"No accepted_task_types for profile '{profile_name}', accepting all task types")

    def set_accepted_task_types(self, task_types: List[str]):
        """
        Set which task types this worker will process.
        Tasks of other types will be returned to the queue.

        Args:
            task_types: List of task type strings to accept
        """
        self.accepted_task_types = task_types
        logger.debug(f"Worker {self.worker_id} configured to accept task types: {task_types}")

    def _setup_github_auth(self):
        """Initialize GitHub authentication for the worker."""
        try:
            logger.info("Initializing GitHub authentication for worker")
            
            # Simple setup - the worker will handle token generation via tasks
            from src.providers.github.auth_service import GitHubAuthService
            
            auth_service = GitHubAuthService()
            
            # Try to setup CLI if token is already available
            import asyncio
            try:
                token_info = asyncio.run(auth_service.get_token_info())
                if token_info.get("authenticated", False):
                    asyncio.run(auth_service.ensure_gh_auth())
                    logger.info("GitHub CLI setup completed - token available")
                else:
                    logger.info("No token available yet - worker ready for token refresh tasks")
            except Exception as e:
                logger.debug(f"Initial token check: {e}")
                logger.info("Worker ready to handle GitHub token generation tasks")
                
        except Exception as e:
            logger.error(f"Failed to initialize GitHub authentication: {e}")
            # Don't fail the worker startup for GitHub auth issues
    
    def _setup_gws_credentials(self):
        """
        Write Google Workspace CLI credentials to disk so `gws` can authenticate.

        Reads gcp.google_docs_credentials_json from config (populated at runtime
        from the GCP__GOOGLE_DOCS_CREDENTIALS_JSON env var via update_from_env).
        Writes the JSON to ~/.config/gws/credentials.json and sets
        GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE so `gws` picks it up automatically.

        If the credential is absent or invalid, logs a warning and skips — the
        worker continues normally and `gws` commands will simply fail at runtime.
        """
        try:
            creds_json = self.config.get("gcp", {}).get("google_docs_credentials_json", "")
            if not creds_json or not creds_json.strip():
                logger.debug("GCP__GOOGLE_DOCS_CREDENTIALS_JSON not set — skipping gws credential setup")
                return

            import json
            creds_path = os.path.expanduser("~/.config/gws/credentials.json")
            os.makedirs(os.path.dirname(creds_path), exist_ok=True)

            # gws expects authorized_user format; ensure the type field is present
            data = json.loads(creds_json)
            data.setdefault("type", "authorized_user")

            with open(creds_path, "w") as f:
                json.dump(data, f)

            os.environ["GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE"] = creds_path
            logger.info(f"gws credentials written to {creds_path}")

        except Exception as e:
            logger.warning(f"Failed to set up gws credentials: {e}")

    def _setup_telemetry(self):
        """Initialize telemetry/metrics for the worker."""
        try:
            logger.info("Initializing telemetry/metrics for worker")
            
            from src.providers.telemetry import setup_telemetry, is_metrics_initialized
            
            # Set service-specific telemetry config for worker service
            telemetry_config = self.config.get("telemetry", {})
            # Set worker-specific service name (override generic default)
            telemetry_config["service_name"] = "swe-agent-worker"
            # Add service label to distinguish worker from API and MCP
            labels = telemetry_config.get("labels", {})
            labels["service"] = "worker"
            telemetry_config["labels"] = labels
            telemetry_config["enabled"] = True
            
            # Initialize metrics if not already initialized
            setup_telemetry(telemetry_config)
            logger.info("Telemetry initialized successfully for worker")

            # Initialize review metrics globally (similar to API's HTTP metrics pattern)
            # This ensures metrics are registered before the metrics server starts serving
            try:
                from src.agents.review_agents.metrics import initialize_review_metrics
                initialize_review_metrics()
            except ImportError:
                # Review metrics module not available (e.g., in task execution worker)
                logger.debug("Review metrics module not available, skipping review metrics initialization")
            except Exception as e:
                logger.warning(f"Failed to initialize review metrics: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Failed to initialize telemetry: {e}", exc_info=True)
            logger.warning("Continuing worker startup without telemetry")
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self.stop()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def _setup_cli_sync_service(self):
        """Initialize GitHub CLI sync service for the worker."""
        try:
            logger.info("Starting GitHub CLI sync service for worker")
            
            # Start CLI sync service in a daemon thread
            import threading
            import asyncio
            
            def run_sync_service():
                """Run the CLI sync service in a separate thread."""
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    async def start_service():
                        from src.providers.github.cli_sync_service import start_cli_sync_service
                        await start_cli_sync_service(sync_interval=300, bot_name=self.github_bot)
                        
                        # Keep the event loop running
                        while not self.should_stop.is_set():
                            await asyncio.sleep(1)
                    
                    loop.run_until_complete(start_service())
                    
                except Exception as e:
                    logger.error(f"CLI sync service failed: {e}")
                finally:
                    loop.close()
            
            # Start in daemon thread so it doesn't block shutdown
            sync_thread = threading.Thread(
                target=run_sync_service,
                daemon=True,
                name="github-cli-sync"
            )
            sync_thread.start()
            
            logger.info("GitHub CLI sync service started for worker")
            
        except Exception as e:
            logger.error(f"Failed to start GitHub CLI sync service: {e}")
            # Don't fail worker startup for CLI sync issues
    
    def _setup_cancellation_monitor(self):
        """Initialize background cancellation monitor for running tasks."""
        try:
            logger.info("Starting background cancellation monitor")
            
            def monitor_loop():
                """Monitor running tasks for cancellation requests."""
                try:
                    while not self.should_stop.is_set():
                        self._check_running_tasks_for_cancellation()
                        time.sleep(5)  # Check every 5 seconds
                except Exception as e:
                    logger.error(f"Cancellation monitor failed: {e}")
                finally:
                    logger.info("Cancellation monitor stopped")
            
            # Start monitor in daemon thread so it doesn't block shutdown
            monitor_thread = threading.Thread(
                target=monitor_loop,
                daemon=True,
                name="task-cancellation-monitor"
            )
            
            # Store reference for clean shutdown and monitoring
            self.monitor_thread = monitor_thread
            monitor_thread.start()
            
            logger.info("Background cancellation monitor started")
            
        except Exception as e:
            logger.error(f"Failed to start cancellation monitor: {e}")
            # Don't fail worker startup for monitor issues
    
    def is_monitor_thread_healthy(self) -> bool:
        """Check if the cancellation monitor thread is running."""
        return hasattr(self, 'monitor_thread') and self.monitor_thread.is_alive()
    
    def register_running_task(self, task_id: str, task_data: Dict[str, Any]):
        """Register a task as currently running."""
        with self.task_lock:
            self.running_tasks[task_id] = {
                'start_time': time.time(),
                'task_data': task_data,

                'task_type': task_data.get('task_type', 'unknown'),
                'cancel_requested': False,
                'process_ids': []  # List of subprocess PIDs for this task
            }
            logger.debug(f"Registered running task: {task_id}")
    
    def unregister_running_task(self, task_id: str):
        """Unregister a task when it completes."""
        with self.task_lock:
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
                logger.debug(f"Unregistered task: {task_id}")
    
    def _check_running_tasks_for_cancellation(self):
        """Check if any running tasks have been cancelled in the database."""
        # Task types that don't use database tracking
        NO_DB_TRACKING_TYPES = ['comment_analysis']

        with self.task_lock:
            running_task_ids = list(self.running_tasks.keys())

        for task_id in running_task_ids:
            try:
                # Get task type from running tasks registry
                with self.task_lock:
                    task_info = self.running_tasks.get(task_id, {})
                    task_type = task_info.get('task_type', 'unknown')

                # Skip database check for tasks that don't use database tracking
                if task_type in NO_DB_TRACKING_TYPES:
                    continue

                # Skip tasks already signalled — avoids log spam while process winds down
                with self.task_lock:
                    already_signalled = self.running_tasks.get(task_id, {}).get('cancel_requested', False)
                if already_signalled:
                    continue

                # Check task status in database
                current_status = task_manager.get_task_status(task_id)
                
                if current_status and current_status.lower() == 'cancelled':
                    logger.info(f"Detected cancelled task {task_id}, requesting cancellation")
                    self._signal_task_cancellation(task_id)
                    
            except Exception as e:
                logger.warning(f"Error checking cancellation for task {task_id}: {e}")
    
    def _signal_task_cancellation(self, task_id: str):
        """Signal cancellation to a running task and terminate associated processes."""
        with self.task_lock:
            if task_id in self.running_tasks:
                self.running_tasks[task_id]['cancel_requested'] = True
                process_ids = self.running_tasks[task_id]['process_ids'].copy()
                logger.info(f"Cancellation requested for task {task_id} with {len(process_ids)} processes")
                
                # Terminate associated processes
                self._terminate_task_processes(task_id, process_ids)
    
    def _terminate_task_processes(self, task_id: str, process_ids: List[int]):
        """Terminate all subprocess PIDs associated with a task."""
        if not process_ids:
            logger.debug(f"No processes to terminate for task {task_id}")
            return
        
        logger.info(f"Terminating {len(process_ids)} processes for task {task_id}")
        
        for pid in process_ids:
            try:
                # Check if process still exists
                if not self._is_process_running(pid):
                    logger.debug(f"Process {pid} already terminated")
                    continue
                
                logger.info(f"Attempting to terminate process {pid} for task {task_id}")
                
                # First try graceful termination (SIGTERM)
                try:
                    logger.debug(f"Sending SIGTERM to process {pid}")
                    os.kill(pid, signal.SIGTERM)
                except OSError as e:
                    if e.errno == 3:  # No such process
                        logger.debug(f"Process {pid} already terminated (no such process)")
                        continue
                    elif e.errno == 1:  # Operation not permitted
                        logger.warning(f"Permission denied for SIGTERM to process {pid}, trying SIGKILL")
                        # Skip to SIGKILL
                        pass
                    else:
                        logger.warning(f"Error sending SIGTERM to process {pid}: {e}")
                        continue
                
                # Give process a chance to terminate gracefully (1 second)
                for attempt in range(10):  # Check every 100ms for 1 second
                    time.sleep(0.1)
                    if not self._is_process_running(pid):
                        logger.info(f"Process {pid} terminated gracefully after {(attempt+1)*100}ms")
                        break
                else:
                    # Force kill if still running after 1 second
                    if self._is_process_running(pid):
                        logger.warning(f"Process {pid} did not terminate gracefully, forcing SIGKILL")
                        try:
                            os.kill(pid, signal.SIGKILL)
                            # Wait longer for SIGKILL to take effect (up to 500ms)
                            for attempt in range(5):
                                time.sleep(0.1)
                                if not self._is_process_running(pid):
                                    logger.info(f"Process {pid} force-killed successfully after {(attempt+1)*100}ms")
                                    break
                            else:
                                # Still running after SIGKILL - this is unusual but possible
                                logger.error(f"Process {pid} survived SIGKILL for task {task_id} - may be zombie or kernel process")
                                
                        except OSError as kill_error:
                            if kill_error.errno == 3:  # No such process
                                logger.debug(f"Process {pid} terminated during SIGKILL attempt")
                            elif kill_error.errno == 1:  # Operation not permitted
                                logger.error(f"Permission denied for SIGKILL to process {pid}")
                            else:
                                logger.error(f"Error sending SIGKILL to process {pid}: {kill_error}")
                
            except Exception as e:
                logger.exception(f"Unexpected error terminating process {pid}: {e}")
    
    def _is_process_running(self, pid: int) -> bool:
        """Check if a process is still running (not zombie)."""
        try:
            # Send signal 0 to check if process exists
            os.kill(pid, 0)
            
            # Additional check: read process status to detect zombies
            try:
                with open(f'/proc/{pid}/stat', 'r') as f:
                    stat_line = f.read()
                    # Third field is the state: Z means zombie
                    fields = stat_line.split()
                    if len(fields) > 2 and fields[2] == 'Z':
                        logger.debug(f"Process {pid} is a zombie")
                        return False
            except (FileNotFoundError, IOError, IndexError):
                # /proc might not be available on macOS, or process might have disappeared
                # Fall back to just the os.kill check
                pass
            
            return True
        except OSError:
            return False
    
    def is_task_cancellation_requested(self, task_id: str) -> bool:
        """Check if cancellation has been requested for a task."""
        with self.task_lock:
            task_info = self.running_tasks.get(task_id, {})
            return task_info.get('cancel_requested', False)
    
    def register_task_process(self, task_id: str, process_id: int):
        """Register a subprocess PID for a running task."""
        with self.task_lock:
            if task_id in self.running_tasks:
                self.running_tasks[task_id]['process_ids'].append(process_id)
                logger.info(f"Registered process {process_id} for task {task_id}")
            else:
                logger.warning(f"Attempted to register process {process_id} for unknown task {task_id}")
    
    def unregister_task_process(self, task_id: str, process_id: int):
        """Unregister a subprocess PID for a task."""
        with self.task_lock:
            if task_id in self.running_tasks:
                try:
                    self.running_tasks[task_id]['process_ids'].remove(process_id)
                    logger.debug(f"Unregistered process {process_id} for task {task_id}")
                except ValueError:
                    logger.warning(f"Process {process_id} not found in task {task_id} registry")
    
    def get_task_processes(self, task_id: str) -> List[int]:
        """Get list of subprocess PIDs for a task."""
        with self.task_lock:
            task_info = self.running_tasks.get(task_id, {})
            return task_info.get('process_ids', []).copy()
    
    def start(self):
        """Start the worker to begin processing tasks."""
        if self.is_running:
            logger.warning("Worker is already running")
            return
        
        self.is_running = True
        self.start_time = time.time()
        
        logger.info(f"Starting SWE Agent Worker {self.worker_id}")
        logger.info(f"Environment: {self.env_name}")
        logger.info(f"Queue type: {self.queue_manager.queue_type}")
        logger.info(f"Max tasks per run: {self.max_tasks_per_run}")
        
        try:
            self._main_loop()
        except Exception as e:
            logger.error(f"Worker encountered fatal error: {e}")
            raise
        finally:
            self._cleanup()
    
    def stop(self):
        """Signal the worker to stop gracefully."""
        logger.info(f"Stopping worker {self.worker_id}")
        self.should_stop.set()
        self.is_running = False
        
        # Wait for monitor thread to finish gracefully
        if hasattr(self, 'monitor_thread') and self.monitor_thread.is_alive():
            logger.info("Waiting for cancellation monitor to stop...")
            self.monitor_thread.join(timeout=10)
            if self.monitor_thread.is_alive():
                logger.warning("Cancellation monitor did not stop within timeout")
            else:
                logger.info("Cancellation monitor stopped gracefully")
        
    
    def _main_loop(self):
        """Main worker loop that continuously processes tasks with concurrent execution."""
        logger.info("Worker main loop started")

        consecutive_empty_polls = 0
        max_empty_polls = 5

        # Calculate max workers for concurrent processing
        max_workers = min(self.max_tasks_per_run, 3)
        logger.info(f"Concurrent task processing enabled with {max_workers} max workers")

        while self.is_running and not self.should_stop.is_set():
            try:
                # Get tasks from queue
                tasks = self.queue_manager.receive_tasks(
                    max_messages=self.max_tasks_per_run,
                    wait_time=20  # Long polling for efficiency
                )

                if not tasks:
                    consecutive_empty_polls += 1
                    if consecutive_empty_polls >= max_empty_polls:
                        logger.debug("No tasks available, worker idling...")
                        consecutive_empty_polls = 0  # Reset counter
                    continue

                consecutive_empty_polls = 0
                logger.info(f"Received {len(tasks)} task(s) to process concurrently")

                # Process tasks concurrently using ThreadPoolExecutor
                with ThreadPoolExecutor(
                    max_workers=max_workers,
                    thread_name_prefix="task-worker"
                ) as executor:
                    # Submit all tasks to the thread pool
                    futures = {}
                    for task_data in tasks:
                        if self.should_stop.is_set():
                            logger.info("Stop signal received, not submitting more tasks")
                            break

                        future = executor.submit(self._process_single_task, task_data)
                        task_id = task_data.get('task_id', 'unknown')
                        futures[future] = task_id

                    # Wait for all tasks to complete or stop signal
                    for future in as_completed(futures.keys()):
                        task_id = futures[future]
                        try:
                            future.result()  # This will raise any exceptions from the task
                        except Exception as e:
                            logger.error(f"Exception from concurrent task {task_id}: {e}")

                        if self.should_stop.is_set():
                            logger.info("Stop signal received during task processing")
                            # Cancel remaining futures
                            for remaining_future in futures.keys():
                                if not remaining_future.done():
                                    remaining_future.cancel()
                            break

                # Log periodic statistics
                self._log_statistics()

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received, stopping worker")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                # Don't break the loop for non-fatal errors
                time.sleep(5)  # Brief pause before retrying

        logger.info("Worker main loop ended")
    
    def _process_single_task(self, task_data: Dict[str, Any]):
        """
        Process a single task and handle the result.
        Thread-safe for concurrent execution.

        Args:
            task_data: Task data from the queue
        """
        task_id = task_data.get('task_id', 'unknown')
        task_type = task_data.get('task_type', 'unknown')
        thread_name = threading.current_thread().name

        # Task type filtering - return to queue if not accepted
        if self.accepted_task_types is not None and task_type not in self.accepted_task_types:
            logger.debug(f"[{thread_name}] Task {task_id} type '{task_type}' not in accepted types, returning to queue")
            if self.queue_manager.return_task_to_queue(task_data):
                return  # Successfully returned to queue
            else:
                logger.error(f"[{thread_name}] Failed to return task {task_id} to queue, will retry on visibility timeout")
                return

        start_time = time.time()
        logger.info(f"[{thread_name}] Processing task {task_id} of type {task_type}")

        try:
            # Register task as running
            if task_id != 'unknown':
                self.register_running_task(task_id, task_data)
            
            # Process the task (now async)
            import asyncio
            result = asyncio.run(self.task_processor.process_task(task_data))
            
            processing_time = time.time() - start_time

            if result.get('success', False):
                logger.info(f"[{thread_name}] Task {task_id} completed successfully in {processing_time:.2f}s")
                with self.stats_lock:
                    self.tasks_processed += 1

                # Debug: Log task_data structure before deletion attempt
                metadata = task_data.get('_queue_metadata', {})
                logger.info(f"[{thread_name}] Attempting to delete task {task_id} with metadata: {metadata}")
                
                # Delete the task from queue on success
                deletion_success = self.queue_manager.delete_task(task_data)
                if not deletion_success:
                    logger.warning(f"[{thread_name}] Failed to delete task {task_id} from queue")
                    logger.warning(f"[{thread_name}] Task data keys: {list(task_data.keys())}")
                    logger.warning(f"[{thread_name}] Queue metadata: {metadata}")
                    logger.warning(f"[{thread_name}] Queue type: {self.queue_manager.queue_type}")
                else:
                    logger.info(f"[{thread_name}] Successfully deleted task {task_id} from queue")

            else:
                logger.error(f"[{thread_name}] Task {task_id} failed: {result.get('error', 'Unknown error')}")
                with self.stats_lock:
                    self.tasks_failed += 1
                
                # For failed tasks, we might want to leave them in the queue
                # to be retried or sent to DLQ automatically by SQS
                # Only delete if it's a permanent failure
                error_msg = result.get('error', '').lower()
                if any(keyword in error_msg for keyword in ['missing parameter', 'invalid', 'configuration']):
                    # Permanent failure, delete from queue
                    self.queue_manager.delete_task(task_data)
                    logger.info(f"[{thread_name}] Deleted permanently failed task {task_id} from queue")

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"[{thread_name}] Exception processing task {task_id}: {e}")
            with self.stats_lock:
                self.tasks_failed += 1

            # Don't delete task on exception - let it retry or go to DLQ

        finally:
            # Always unregister task when processing completes
            if task_id != 'unknown':
                self.unregister_running_task(task_id)

            # Log completion (calculate processing time if not already done)
            if 'processing_time' not in locals():
                processing_time = time.time() - start_time
            logger.debug(f"[{thread_name}] Task {task_id} processing completed in {processing_time:.2f}s")
    
    def _log_statistics(self):
        """Log worker statistics periodically."""
        # Read counters under lock for consistency
        with self.stats_lock:
            processed = self.tasks_processed
            failed = self.tasks_failed

        # Log outside lock to avoid holding it during I/O
        if processed % 10 == 0 and processed > 0:
            uptime = time.time() - (self.start_time or time.time())
            total = processed + failed
            success_rate = (processed / total) * 100 if total > 0 else 0

            logger.info(f"Worker {self.worker_id} Statistics:")
            logger.info(f"  Uptime: {uptime:.0f}s")
            logger.info(f"  Tasks processed: {processed}")
            logger.info(f"  Tasks failed: {failed}")
            logger.info(f"  Success rate: {success_rate:.1f}%")
    
    def _cleanup(self):
        """Cleanup resources before shutting down."""
        logger.info(f"Worker {self.worker_id} cleaning up...")

        # Flush and shut down OTEL event emitter
        try:
            from src.providers.telemetry.otel_events import shutdown_otel_events
            shutdown_otel_events()
        except Exception as e:
            logger.warning(f"OTEL event emitter shutdown failed: {e}")
        
        # Log final statistics
        if self.start_time:
            uptime = time.time() - self.start_time

            # Read counters under lock
            with self.stats_lock:
                processed = self.tasks_processed
                failed = self.tasks_failed

            logger.info(f"Final Statistics for worker {self.worker_id}:")
            logger.info(f"  Total uptime: {uptime:.0f}s")
            logger.info(f"  Total tasks processed: {processed}")
            logger.info(f"  Total tasks failed: {failed}")

        logger.info(f"Worker {self.worker_id} shutdown complete")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current worker status and statistics."""
        uptime = time.time() - (self.start_time or time.time()) if self.start_time else 0

        # Read counters under lock for consistency
        with self.stats_lock:
            processed = self.tasks_processed
            failed = self.tasks_failed

        return {
            'worker_id': self.worker_id,
            'is_running': self.is_running,
            'environment': self.env_name,
            'queue_type': self.queue_manager.queue_type,
            'uptime_seconds': uptime,
            'tasks_processed': processed,
            'tasks_failed': failed,
            'queue_stats': self.queue_manager.get_queue_stats(),
            'supported_task_types': self.task_processor.get_supported_task_types()
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform a health check of the worker and its components."""
        try:
            # Check queue manager health
            queue_stats = self.queue_manager.get_queue_stats()
            queue_healthy = bool(queue_stats and not any('error' in stats for stats in queue_stats.values()))
            
            # Check if worker is responsive
            worker_healthy = self.is_running and not self.should_stop.is_set()
            
            overall_health = queue_healthy and worker_healthy
            
            return {
                'healthy': overall_health,
                'worker_running': worker_healthy,
                'queue_healthy': queue_healthy,
                'queue_stats': queue_stats,
                'last_check': time.time()
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'error': str(e),
                'last_check': time.time()
            } 