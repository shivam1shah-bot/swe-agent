"""
Bank Integration Service for SWE Agent
This service provides bank integration functionality using LangGraph workflows.
"""

import logging
import os
import json
import time
import asyncio
from datetime import datetime
from typing import Dict, Any, List
from dataclasses import dataclass
import hashlib
import random
import string

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage

from src.services.agents_catalogue.base_service import BaseAgentsCatalogueService
from src.providers.context import Context
from src.providers.github.auth_service import GitHubAuthService
from .bank_integration_state import BankIntegrationState
from .repository_config import BankRepositoryConfig
from src.agents.autonomous_agent import AutonomousAgentTool

logger = logging.getLogger(__name__)


def _build_agent_prompt(repository_url: str, branch: str, user_prompt: str) -> str:
    """Build clone + commit + PR prompt for bank integration agent tasks."""
    url = (repository_url or "").strip()
    if url.startswith("https://github.com/"):
        path_part = url[len("https://github.com/"):]
    elif url.startswith("git@github.com:"):
        path_part = url[len("git@github.com:"):]
    else:
        path_part = url
    if path_part.endswith(".git"):
        path_part = path_part[:-4]
    parts = [p for p in path_part.split("/") if p]
    owner, repo = (parts[0], parts[1]) if len(parts) >= 2 else (None, None)

    if owner and repo:
        clone_cmd = f"gh repo clone {owner}/{repo} -- --depth 1 --single-branch --branch master\ncd {repo}"
    else:
        clone_cmd = f"gh repo clone {repository_url} -- --depth 1 --single-branch --branch master"

    return (
        f"Repository Setup (use gh CLI only):\n{clone_cmd}\n"
        f"Use the feature branch '{branch}'. If it does not exist, create it from master. Never commit to main or master.\n\n"
        "MANDATORY: Ensure that all modifications are committed, pushed to the feature branch, and a DRAFT PR is created as described below.\n"
        "After implementing the requested changes:\n"
        "0. Verify the code builds/compiles before staging any changes:\n"
        "   - Detect the language from project files and run only if the tool is available:\n"
        "     go.mod → run: go build ./...\n"
        "     package.json with a 'build' script → run: npm run build\n"
        "     requirements.txt/setup.py → run: python -m py_compile <each changed .py file>\n"
        "     Java/Kotlin (pom.xml/build.gradle) → skip (build tools not available in this environment)\n"
        "   - If the build fails, fix ALL errors before proceeding.\n"
        "   - If none of the above apply, skip this step.\n"
        "1. Stage all changes: git add -A\n"
        f'2. Commit with a clear message: git commit -m "chore: apply requested changes via autonomous agent"\n'
        f"3. Push the branch: git push -u origin {branch}\n"
        "4. Open a DRAFT Pull Request using gh CLI with a meaningful title and body:\n"
        '   gh pr create --title "chore: apply requested changes via autonomous agent" --body "Automated changes by autonomous agent." --draft\n\n'
        f"User Task:\n{user_prompt}"
    )


class BankIntegrationService(BaseAgentsCatalogueService):
    """
    Bank Integration Service for Agents Catalogue.
    
    Automates the integration of new banks across multiple services:
    integrations-go, FTS, Payouts, and X-Balance using LangGraph workflow.
    """
    
    def __init__(self):
        """Initialize the Bank Integration Service."""
        self.logger = logger
        self._github_auth = None  # Lazy initialization
        self.capabilities = [
            "bank_integration",
            "multi_service_updates", 
            "automated_testing",
            "pr_creation",
            "langgraph_workflow",
            "parallel_processing"
        ]
        self.version = "1.0.0"
        
        # AI code generation is handled by AutonomousAgentTool which uses Claude
    
    @property
    def github_auth(self) -> GitHubAuthService:
        """Lazy property for GitHub auth service."""
        if self._github_auth is None:
            self._github_auth = GitHubAuthService()
        return self._github_auth
    
    async def _setup_git_authentication(self, repository_url: str) -> Dict[str, Any]:
        """
        Setup Git authentication using GitHubAuthService or manual tokens.
        
        Args:
            repository_url: GitHub repository URL
            
        Returns:
            Dictionary with authentication setup results
        """
        try:
            # Check authentication mode from environment
            auth_mode = os.getenv("GITHUB_AUTH_MODE", "service").lower()
            
            if auth_mode == "manual":
                self.logger.info(f"Using manual GitHub authentication for repository: {repository_url}")
                return {
                    "success": True,
                    "message": "Manual Git authentication configured via environment variables",
                    "auth_mode": "manual",
                    "token_available": bool(os.getenv("GH_TOKEN")),
                    "git_config_setup": True,  # Handled by Docker environment
                    "gh_auth_setup": True     # Handled by Docker environment
                }
            
            # Production mode: Use GitHubAuthService
            self.logger.info(f"Setting up dynamic Git authentication for repository: {repository_url}")
            
            # Get current token
            token = await self.github_auth.get_token()
            
            if not token:
                return {
                    "success": False,
                    "error": "No GitHub token available",
                    "message": "Failed to obtain GitHub authentication token"
                }
            
            # Setup git config
            setup_result = await self.github_auth.setup_git_config()
            
            # Ensure gh CLI is authenticated
            auth_result = await self.github_auth.ensure_gh_auth()
            
            self.logger.info(f"Git authentication setup completed - token available: {bool(token)}, "
                           f"git config: {setup_result.get('success', False)}, "
                           f"gh auth: {auth_result.get('success', False)}")
            
            return {
                "success": True,
                "message": "Dynamic Git authentication configured successfully",
                "auth_mode": "service",
                "token_available": bool(token),
                "git_config_setup": setup_result.get("success", False),
                "gh_auth_setup": auth_result.get("success", False)
            }
        except Exception as e:
            self.logger.error(f"Git authentication setup failed: {str(e)}")
            return {
                "success": False,
                "error": f"Git authentication setup failed: {str(e)}",
                "message": "Failed to configure Git authentication"
            }
    
    def _get_git_workflow_instructions(self, repository_name: str, bank_name: str, service_name: str, 
                                      commit_details: str, pr_body: str) -> str:
        """Generate complete git workflow instructions for any service."""
        return f"""
### Git Workflow Instructions (MANDATORY SEQUENCE):

**STEP: Repository Setup and Branch Creation**
```bash
# Clone repository with authentication
gh repo clone razorpay/{repository_name}
cd {repository_name} || export REPO_DIR="/tmp/$(basename $(pwd))/{repository_name}" && cd "$REPO_DIR" && pwd || export SHELL_PWD="$REPO_DIR" && cd "$SHELL_PWD"

# Create unique branch with timestamp  
git checkout -b feature/{repository_name}-{bank_name}-integration-$(date +%Y%m%d-%H%M%S)

# Always verify directory
pwd
ls -la
```

**STEP: Commit and Push Changes (After making all code changes)**
```bash
# Stage all changes
git add .

# Commit with descriptive message
git commit -m "chore: integrate {bank_name.upper()} bank into {service_name} service

{commit_details}

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

# Push to remote branch
git push -u origin $(git branch --show-current)
```

**STEP: Create Draft Pull Request**
```bash
gh pr create --title "chore: integrate {bank_name.upper()} bank into {service_name} service" --body "$(cat <<'EOF'
{pr_body}
EOF
)" --draft
```

**CRITICAL**: Execute each git step in the exact order specified. DO NOT skip any steps.
"""

    def _get_dynamic_git_authentication_instructions(self) -> str:
        """Get Git authentication instructions based on current environment mode."""
        auth_mode = os.getenv("GITHUB_AUTH_MODE", "service").lower()
        
        if auth_mode == "manual":
            return """
### Git Push Authentication (MANDATORY SEQUENCE):

When git push fails with authentication errors, ALWAYS try these steps in order:

1. **First attempt**: Standard git push
   `git push -u origin <branch-name>`

2. **If step 1 fails**: Embed token in remote URL  
   ```bash
   git remote set-url origin https://$(gh auth token)@github.com/razorpay/<repo>.git
   git push -u origin <branch-name>
   ```

3. **If step 2 fails**: Alternative token embedding
   ```bash  
   TOKEN=$(gh auth token)
   git remote set-url origin https://${{TOKEN}}@github.com/razorpay/<repo>.git
   git push -u origin <branch-name>
   ```

4. **Verify success**: Check remote branch exists
   `git ls-remote origin <branch-name>`
"""
        else:
            return """
### Git Authentication (Automatic):

The system will automatically configure GitHub authentication for you:

✅ **Automatic Setup**: Authentication tokens are managed automatically
✅ **Dynamic Refresh**: Tokens refresh automatically when needed  
✅ **Multi-Service Support**: Works across all GitHub repositories
✅ **No Manual Configuration**: No token embedding required

**For Git operations, simply use standard commands:**
- `gh repo clone <owner>/<repo>` - Automatic authentication
- `git push origin <branch-name>` - Uses managed credentials
- `gh pr create ...` - Authenticated automatically

**If you encounter authentication issues:**
1. The system will automatically retry with fresh tokens
2. Authentication is managed by GitHubAuthService
3. No manual intervention required
"""

    @property
    def description(self) -> str:
        """Service description."""
        return "Automates bank integration across multiple services: integrations-go, FTS, Payouts, X-Balance"
    
    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronous execute for API calls - queues the task and returns immediately."""
        try:
            # Validate required parameters
            self._validate_parameters(parameters)
            
            # Queue the task using sync queue integration
            from src.tasks.queue_integration import queue_integration
            
            if not queue_integration.is_queue_available():
                return {
                    "status": "failed",
                    "message": "Queue not available",
                    "metadata": {"error": "Queue not available"}
                }
            
            self.logger.info("Submitting bank integration task to queue",
                           extra={
                               "bank_name": parameters.get("bank_name"),
                               "version": parameters.get("version"),
                               "services": self._get_enabled_services(parameters)
                           })
            
            # Submit to queue with bank-integration-specific task type
            task_id = queue_integration.submit_agents_catalogue_task(
                usecase_name="bank-integration", 
                parameters=parameters,
                metadata={
                    "service_type": "bank_integration",
                    "execution_mode": "async",
                    "priority": "normal",
                    "bank_name": parameters.get("bank_name"),
                    "version": parameters.get("version"),
                    "services": self._get_enabled_services(parameters),
                    "workflow_type": "langgraph"
                }
            )
            
            if task_id:
                self.logger.info("Bank integration task queued successfully",
                               extra={
                                   "task_id": task_id,
                                   "bank_name": parameters.get("bank_name"),
                                   "version": parameters.get("version")
                               })
                return {
                    "status": "queued", 
                    "message": f"Bank integration for {parameters.get('bank_name')} queued successfully",
                    "task_id": task_id,
                    "workflow_type": "langgraph",
                    "metadata": {
                        "bank_name": parameters.get("bank_name"),
                        "version": parameters.get("version"),
                        "services": self._get_enabled_services(parameters),
                        "queued_at": self._get_current_timestamp()
                    }
                }
            else:
                return {
                    "status": "failed",
                    "message": "Failed to queue bank integration", 
                    "metadata": {"error": "Failed to submit to queue"}
                }
                
        except Exception as e:
            self.logger.error(f"Bank integration submission failed: {e}")
            return {
                "status": "failed",
                "message": f"Failed to process bank integration request: {str(e)}",
                "metadata": {
                    "error": str(e)
                }
            }
    
    def async_execute(self, parameters: Dict[str, Any], ctx: Context) -> Dict[str, Any]:
        """
        Asynchronous execute for worker processing - follows standard SWE Agent pattern.
        
        Args:
            parameters: Service-specific parameters for bank integration
            ctx: Execution context with task_id, metadata, cancellation, and logging correlation
            
        Returns:
            Dictionary containing:
                - status: "completed" or "failed"
                - message: Status message  
                - pr_urls: List of created PR URLs
                - files_modified: List of files modified
        """
        execution_start = time.time()
        
        try:
            # Extract task information from context
            task_id = self.get_task_id(ctx)
            log_ctx = self.get_logging_context(ctx)
            
            self.logger.info("Starting async bank integration using AutonomousAgentTool", extra=log_ctx)
            
            # Check if context is already done before starting
            if self.check_context_done(ctx):
                error_msg = "Context is done before bank integration"
                if ctx.is_cancelled():
                    error_msg = "Context was cancelled before bank integration"
                elif ctx.is_expired():
                    error_msg = "Context expired before bank integration"
                
                self.logger.warning(error_msg, extra=log_ctx)
                return {
                    "status": "failed",
                    "message": error_msg,
                    "metadata": {
                        "error": error_msg,
                        "task_id": task_id,
                        "correlation_id": ctx.get("log_correlation_id")
                    }
                }
            
            # Validate required parameters
            self._validate_parameters(parameters)
            
            # Call the autonomous agent (following standard SWE Agent pattern)
            agent_result = self._call_autonomous_agent(parameters, ctx)
            
            execution_time = time.time() - execution_start
            
            # Process and format the results
            if agent_result.get("success"):
                return {
                    "status": "completed",
                    "message": f"Successfully integrated {parameters.get('bank_name')} bank across selected services",
                    "pr_urls": agent_result.get("pr_urls", []),
                    "files_modified": agent_result.get("files_modified", []),
                    "execution_time": execution_time,
                    "agent_result": agent_result,
                    "metadata": {
                        "bank_name": parameters.get("bank_name"),
                        "version": parameters.get("version"),
                        "services": self._get_enabled_services(parameters),
                        "task_id": task_id,
                        "correlation_id": ctx.get("log_correlation_id"),
                        "execution_mode": "async",
                        "processed_by_worker": True
                    }
                }
            else:
                return {
                    "status": "failed",
                    "message": f"Failed to integrate {parameters.get('bank_name')} bank: {agent_result.get('error', 'Unknown error')}",
                    "error": agent_result.get("error"),
                    "execution_time": execution_time,
                    "agent_result": agent_result,
                    "metadata": {
                        "error": agent_result.get("error"),
                        "task_id": task_id,
                        "correlation_id": ctx.get("log_correlation_id") if ctx else None
                    }
                }
            
        except Exception as e:
            execution_time = time.time() - execution_start
            
            # Try to get context info if available
            task_id = None
            log_ctx = {}
            try:
                task_id = self.get_task_id(ctx)
                log_ctx = self.get_logging_context(ctx)
            except:
                pass
            
            self.logger.error("Failed to generate bank integration", extra={
                **log_ctx,
                "error": str(e),
                "error_type": type(e).__name__,
                "execution_time": execution_time
            })
            
            return {
                "status": "failed",
                "message": f"Failed to generate bank integration: {str(e)}",
                "error": str(e),
                "execution_time": execution_time,
                "metadata": {
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "task_id": task_id,
                    "correlation_id": ctx.get("log_correlation_id") if ctx else None
                }
            }
    
    def _call_autonomous_agent(self, parameters: Dict[str, Any], ctx: Context) -> Dict[str, Any]:
        """
        Call the autonomous agent using the standard SWE Agent pattern.
        Handles multiple repositories by making separate calls for each.
        
        Args:
            parameters: Service-specific parameters
            ctx: Execution context
            
        Returns:
            Agent execution results with aggregated PR URLs and files
        """
        try:
            # Extract task information from context
            task_id = self.get_task_id(ctx)
            log_ctx = self.get_logging_context(ctx)
            
            bank_name = parameters.get("bank_name", "").lower()
            bank_upper = bank_name.upper()
            version = parameters.get("version", "v3")
            services = self._get_enabled_services(parameters)
            
            self.logger.info("Starting autonomous agent execution for multiple repositories",
                           extra={
                               **log_ctx,
                               "bank_name": bank_name,
                               "version": version,
                               "services": services,
                               "repository_count": len(services)
                           })
            
            # Results aggregation
            all_pr_urls = []
            all_files_modified = []
            successful_services = []
            failed_services = []
            
            # Process each repository separately (correct SWE Agent pattern)
            if "xbalance" in services:
                result = self._call_single_repository_agent(
                    repository_url="https://github.com/razorpay/x-balances",
                    branch_name=f"feature/xbalance-{bank_name}-integration-{self._generate_random_suffix()}", 
                    service_prompt=self._get_xbalance_service_prompt(bank_name, bank_upper, version),
                    task_id=task_id,
                    log_ctx=log_ctx
                )
                if result.get("success"):
                    successful_services.append("xbalance")
                    all_pr_urls.extend(result.get("pr_urls", []))
                    all_files_modified.extend(result.get("files_modified", []))
                else:
                    failed_services.append("xbalance")
            
            if "fts" in services:
                result = self._call_single_repository_agent(
                    repository_url="https://github.com/razorpay/fts",
                    branch_name=f"feature/fts-{bank_name}-{version}-integration-{self._generate_random_suffix()}",
                    service_prompt=self._get_fts_service_prompt(bank_name, bank_upper, version),
                    task_id=task_id,
                    log_ctx=log_ctx
                )
                if result.get("success"):
                    successful_services.append("fts")
                    all_pr_urls.extend(result.get("pr_urls", []))
                    all_files_modified.extend(result.get("files_modified", []))
                else:
                    failed_services.append("fts")
            
            if "payouts" in services:
                result = self._call_single_repository_agent(
                    repository_url="https://github.com/razorpay/payouts",
                    branch_name=f"feature/payouts-{bank_name}-integration-{self._generate_random_suffix()}",
                    service_prompt=self._get_payouts_service_prompt(bank_name, bank_upper, version),
                    task_id=task_id,
                    log_ctx=log_ctx
                )
                if result.get("success"):
                    successful_services.append("payouts")
                    all_pr_urls.extend(result.get("pr_urls", []))
                    all_files_modified.extend(result.get("files_modified", []))
                else:
                    failed_services.append("payouts")
            
            if "integrations-go" in services:
                result = self._call_single_repository_agent(
                    repository_url="https://github.com/razorpay/integrations-go",
                    branch_name=f"feature/integrations-go-{bank_name}-integration-{self._generate_random_suffix()}",
                    service_prompt=self._get_integrations_go_service_prompt(bank_name, bank_upper, version),
                    task_id=task_id,
                    log_ctx=log_ctx
                )
                if result.get("success"):
                    successful_services.append("integrations-go")
                    all_pr_urls.extend(result.get("pr_urls", []))
                    all_files_modified.extend(result.get("files_modified", []))
                else:
                    failed_services.append("integrations-go")
            
            if "terminals" in services:
                result = self._call_single_repository_agent(
                    repository_url="https://github.com/razorpay/terminals",
                    branch_name=f"feature/terminals-{bank_name}-integration-{self._generate_random_suffix()}",
                    service_prompt=self._get_terminals_service_prompt(bank_name, bank_upper, version),
                    task_id=task_id,
                    log_ctx=log_ctx
                )
                if result.get("success"):
                    successful_services.append("terminals")
                    all_pr_urls.extend(result.get("pr_urls", []))
                    all_files_modified.extend(result.get("files_modified", []))
                else:
                    failed_services.append("terminals")
            
            if "kube-manifests" in services:
                result = self._call_single_repository_agent(
                    repository_url="https://github.com/razorpay/kube-manifests",
                    branch_name=f"feature/kube-manifests-{bank_name}-integration-{self._generate_random_suffix()}",
                    service_prompt=self._get_kube_manifests_service_prompt(bank_name, bank_upper, version),
                    task_id=task_id,
                    log_ctx=log_ctx
                )
                if result.get("success"):
                    successful_services.append("kube-manifests")
                    all_pr_urls.extend(result.get("pr_urls", []))
                    all_files_modified.extend(result.get("files_modified", []))
                else:
                    failed_services.append("kube-manifests")
            
            # Determine overall success
            total_services = len(services)
            successful_count = len(successful_services)
            
            self.logger.info("Bank integration autonomous agent execution completed",
                           extra={
                               **log_ctx,
                               "total_services": total_services,
                               "successful_services": successful_count,
                               "failed_services": len(failed_services),
                               "pr_count": len(all_pr_urls),
                               "files_modified_count": len(all_files_modified)
                           })
            
            if successful_count > 0:
                return {
                    "success": True,
                    "message": f"Successfully integrated {bank_upper} bank in {successful_count}/{total_services} services",
                    "pr_urls": all_pr_urls,
                    "files_modified": all_files_modified,
                    "successful_services": successful_services,
                    "failed_services": failed_services,
                    "partial_success": len(failed_services) > 0
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to integrate {bank_upper} bank in all {total_services} services",
                    "message": f"All service integrations failed",
                    "failed_services": failed_services
                }
            
        except Exception as e:
            # Ensure log_ctx exists for error logging
            if 'log_ctx' not in locals():
                log_ctx = {}
            
            self.logger.error("Autonomous agent execution failed",
                            extra={
                                **log_ctx,
                                "error": str(e),
                                "error_type": type(e).__name__,
                                "bank_name": parameters.get("bank_name")
                            })
            
            return {
                "success": False,
                "error": f"Autonomous agent execution failed: {str(e)}",
                "message": "Failed to complete bank integration using autonomous agent"
            }
    
    def _call_single_repository_agent(self, repository_url: str, branch_name: str, service_prompt: str, task_id: str, log_ctx: dict) -> Dict[str, Any]:
        """
        Call AutonomousAgentTool for a single repository (correct SWE Agent pattern).
        
        Args:
            repository_url: GitHub repository URL
            branch_name: Feature branch name
            service_prompt: Service-specific prompt
            task_id: Task ID
            log_ctx: Logging context
            
        Returns:
            Agent execution result for this repository
        """
        import tempfile
        try:
            self.logger.info(f"Starting autonomous agent for repository: {repository_url}",
                           extra={**log_ctx, "repository_url": repository_url, "branch_name": branch_name})

            # Create temporary working directory
            temp_dir = tempfile.mkdtemp(prefix=f"bank-integration-{task_id}-", suffix="-workspace")

            combined_prompt = _build_agent_prompt(
                repository_url=repository_url,
                branch=branch_name,
                user_prompt=service_prompt
            )
            
            # Create autonomous agent tool instance
            agent_tool = AutonomousAgentTool()
            
            # Call with proper parameters (following AutonomousAgentService pattern)
            agent_params = {
                "prompt": combined_prompt,
                "task_id": task_id,
                "working_dir": temp_dir,
                "repository_url": repository_url,
                "branch": branch_name,
                "agent_name": "bank-integration",
            }
            
            result = agent_tool.execute(agent_params)
            
            # Process results
            success = result.get("success", False)
            pr_urls = []
            files_modified = []
            
            if "pr_urls" in result:
                pr_urls = result["pr_urls"] if isinstance(result["pr_urls"], list) else [result["pr_urls"]]
            elif "pr_url" in result:
                pr_urls = [result["pr_url"]]
                
            if "files_modified" in result:
                files_modified = result["files_modified"] if isinstance(result["files_modified"], list) else [result["files_modified"]]
            elif "files" in result:
                files_modified = result["files"] if isinstance(result["files"], list) else [result["files"]]
            
            self.logger.info(f"Repository agent completed: {repository_url}",
                           extra={
                               **log_ctx,
                               "repository_url": repository_url,
                               "success": success,
                               "pr_count": len(pr_urls),
                               "files_count": len(files_modified)
                           })
            
            return {
                "success": success,
                "pr_urls": pr_urls,
                "files_modified": files_modified,
                "error": result.get("error"),
                "repository_url": repository_url,
                "branch_name": branch_name,
                "agent_result": result
            }
            
        except Exception as e:
            self.logger.error(f"Repository agent failed: {repository_url}",
                            extra={
                                **log_ctx,
                                "repository_url": repository_url,
                                "error": str(e),
                                "error_type": type(e).__name__
                            })
            
            return {
                "success": False,
                "error": str(e),
                "pr_urls": [],
                "files_modified": [],
                "repository_url": repository_url,
                "branch_name": branch_name
            }
    
    def _get_xbalance_service_prompt(self, bank_name: str, bank_upper: str, version: str) -> str:
        """Get X-Balance service integration prompt."""
        xbalance_reference = self._get_xbalance_job_reference()
        
        return f"""
## X-BALANCE SERVICE INTEGRATION for {bank_upper}

You are integrating {bank_upper} bank into the x-balances service. 

### Required Files to Create:
1. **internal/job/balanceFetch/{bank_name}/balance_fetch.go**
2. **internal/job/balanceFetch/{bank_name}/balance_fetch_test.go**

### Configuration Files to Update:
1. **internal/constant/constant.go** - Add rate limiter entry:
   ```go
   "{bank_name}": getMutexBasedTokenBucketRateLimiter(5, time.Second),
   ```

2. **pkg/log/code.go** - Add log constant:
   ```go
   {bank_upper}FetchBalanceWorkerTimeTaken = "fetch_balance_worker_time_taken"
   ```

### Reference Implementation:
{xbalance_reference}

### Instructions:
1. Use the exact patterns from the reference implementation
2. Replace BANKNAME with {bank_name} and BANKUPPER with {bank_upper}
3. Follow the worker.Job pattern for all job implementations
4. Include proper error handling and logging
5. Use tab indentation for Go files
6. Test your implementation
"""
    
    def _create_bank_integration_prompt(self, parameters: Dict[str, Any]) -> str:
        """
        Create comprehensive prompt for bank integration (from server1.py logic).
        """
        bank_name = parameters.get("bank_name", "").lower()
        bank_upper = bank_name.upper()
        version = parameters.get("version", "v3")
        
        # Get enabled services
        services = self._get_enabled_services(parameters)
        services_list = ", ".join(services)
        
        prompt = f"""
You are a senior Go developer working on bank integration across multiple services. You will integrate {bank_upper} bank into the following services: {services_list}

## TASK OVERVIEW:
Integrate {bank_upper} bank across multiple payment services using the exact patterns from existing bank implementations.

## BANK DETAILS:
- Bank Name: {bank_upper} 
- Version: {version}
- Services to integrate: {services_list}

## STEP-BY-STEP INTEGRATION PROCESS:

"""

        # Add service-specific sections based on enabled services
        if "integrations_go" in services:
            prompt += self._get_integrations_go_prompt_section(bank_name, bank_upper, version)
        
        if "fts" in services:
            prompt += self._get_fts_prompt_section(bank_name, bank_upper, version)
            
        if "payouts" in services:
            prompt += self._get_payouts_prompt_section(bank_name, bank_upper, version)
            
        if "xbalance" in services:
            prompt += self._get_xbalance_prompt_section(bank_name, bank_upper, version)
        
        prompt += f"""

## FINAL STEPS:
1. Commit all changes with meaningful commit messages
2. Create Pull Requests for all modified repositories
3. Provide summary of all changes made

## SUCCESS CRITERIA:
- All {len(services)} services have {bank_upper} bank integration
- All code follows existing patterns exactly
- All configuration files are updated
- Pull requests are created successfully

Begin the integration process now.
"""
        
        return prompt
    
    def _get_xbalance_prompt_section(self, bank_name: str, bank_upper: str, version: str) -> str:
        """Get X-Balance service integration prompt section."""
        xbalance_reference = self._get_xbalance_job_reference()
        
        return f"""
### STEP 1: X-BALANCE SERVICE INTEGRATION

#### Repository Setup:
```bash
gh repo clone razorpay/x-balances
cd x-balances
git checkout -b feature/xbalance-{bank_name}-integration-$(date +%s)
```

**DIRECTORY RULES**: Always use absolute paths and verify directory navigation.

#### Required Files:
1. **x-balances/internal/job/balanceFetch/{bank_name}/balance_fetch.go**
2. **x-balances/internal/job/balanceFetch/{bank_name}/balance_fetch_test.go**

#### Configuration Updates:
1. **x-balances/internal/constant/constant.go** - Add rate limiter:
   ```go
   "{bank_name}": getMutexBasedTokenBucketRateLimiter(5, time.Second),
   ```

2. **x-balances/pkg/log/code.go** - Add log constant:
   ```go
   {bank_upper}FetchBalanceWorkerTimeTaken = "fetch_balance_worker_time_taken"
   ```

#### Reference Pattern:
{xbalance_reference}

Replace BANKNAME with {bank_name}, BANKUPPER with {bank_upper} in the reference pattern.

"""

    def _get_fts_prompt_section(self, bank_name: str, bank_upper: str, version: str) -> str:
        """Get FTS service integration prompt section."""
        return f"""
### STEP 2: FTS SERVICE INTEGRATION

#### Repository Setup:
```bash
gh repo clone razorpay/fts
cd fts
git checkout -b feature/fts-{bank_name}-{version}-integration-$(date +%s)
```

#### Required Files (Generate in order):
1. **fts/{bank_name}/{version}/constants.go** - Bank constants and configurations
2. **fts/{bank_name}/{version}/error_code.go** - Error code definitions
3. **fts/{bank_name}/{version}/gateway_model.go** - Data structures
4. **fts/{bank_name}/{version}/base.go** - Base functionality
5. **fts/{bank_name}/{version}/gateway_error_mapper.go** - Error mapping
6. **fts/{bank_name}/{version}/action_store.go** - Action routing logic

#### Configuration:
Update **env.default.toml** with {bank_upper} specific configuration sections.

Use IDFC implementation as reference pattern.

"""

    def _get_payouts_prompt_section(self, bank_name: str, bank_upper: str, version: str) -> str:
        """Get Payouts service integration prompt section."""
        return f"""
### STEP 3: PAYOUTS SERVICE INTEGRATION

#### Repository Setup:
```bash
gh repo clone razorpay/payouts
cd payouts
git checkout -b feature/payouts-{bank_name}-integration-$(date +%s)
```

#### Required Files:
1. Bank-specific payout implementations
2. Model definitions for payout requests/responses
3. Configuration updates
4. Test files

Follow existing bank patterns for {bank_upper} integration.

"""

    def _get_integrations_go_prompt_section(self, bank_name: str, bank_upper: str, version: str) -> str:
        """Get Integrations-Go service integration prompt section."""
        return f"""
### STEP 4: INTEGRATIONS-GO SERVICE INTEGRATION

#### Repository Setup:
```bash
gh repo clone razorpay/integrations-go
cd integrations-go
git checkout -b feature/integrations-go-{bank_name}-integration-$(date +%s)
```

#### Required Files:
1. Gateway implementations for payment processing
2. Model definitions
3. Configuration updates
4. Integration tests

Follow existing gateway patterns for {bank_upper} integration.

"""
    
    def _process_agent_results(self, result: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process autonomous agent results (similar to other services).
        """
        if not result.get("success", False):
            return {
                "success": False,
                "error": result.get("error", "Unknown error from autonomous agent"),
                "message": f"Failed to integrate {parameters.get('bank_name')} bank",
                "pr_urls": [],
                "files_modified": []
            }
        
        # Extract PR URLs and files from agent result
        pr_urls = []
        files_modified = []
        
        # The AutonomousAgentTool should provide these in its result
        if "pr_urls" in result:
            pr_urls = result["pr_urls"]
        elif "pr_url" in result:
            pr_urls = [result["pr_url"]]
        
        if "files_modified" in result:
            files_modified = result["files_modified"]
        elif "files" in result:
            files_modified = result["files"]
        
        return {
            "success": True,
            "message": f"Successfully integrated {parameters.get('bank_name')} bank",
            "pr_urls": pr_urls,
            "files_modified": files_modified,
            "agent_output": result.get("output", ""),
            "agent_result": result
        }
    
    def handle_bank_integration_task(self, task_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a bank integration task using LangGraph workflow.
        
        Args:
            task_id: The ID of the task
            parameters: The parameters for the task
            
        Returns:
            The result of the task
        """
        try:
            self.logger.info(f"Processing bank integration LangGraph task {task_id}")
            self.log_behavior(task_id, "LangGraph Task Initiated", "Starting LangGraph workflow for bank integration")
            
            # Validate parameters
            required_params = ["bank_name", "version"]
            for param in required_params:
                if param not in parameters:
                    error_msg = f"Missing required parameter: {param}"
                    self.log_behavior(task_id, "Task Failed", error_msg)
                    return {
                        "success": False,
                        "error": error_msg
                    }
            
            # Create the workflow graph
            workflow_graph = self.create_bank_integration_graph()
            
            # Initialize state
            initial_state = BankIntegrationState(
                task_id=task_id,
                bank_name=parameters["bank_name"],
                version=parameters.get("version", "v3"),
                branch_name=parameters.get("branch_name"),
                bank_documentation=parameters.get("bank_documentation"),
                bank_doc_filename=parameters.get("bank_doc_filename"),
                enable_integrations_go=parameters.get("enable_integrations_go", True),
                enable_fts=parameters.get("enable_fts", True),
                enable_payouts=parameters.get("enable_payouts", True),
                enable_xbalance=parameters.get("enable_xbalance", True),
                enable_terminals=parameters.get("enable_terminals", True),
                enable_kube_manifests=parameters.get("enable_kube_manifests", True),
                messages=[HumanMessage(content=f"Integrate {parameters['bank_name']} bank")],
                current_step="initialize",
                completed_steps=[],
                failed_steps=[],
                repositories={},
                working_branch={},
                agent_instances={},
                agent_contexts={},
                integrations_go_result=None,
                fts_result=None,
                payouts_result=None,
                xbalance_result=None,
                terminals_result=None,
                kube_manifests_result=None,
                workflow_summary={},
                max_iterations=parameters.get("max_iterations", 50),
                current_iteration=0,
                validation_result=None,
                unit_test_result=None,
                integration_test_result=None,
                pr_urls=[],
                git_setup_status={},
                commit_status={},
                push_status={},
                error_messages=[],
                retry_count=0,
                max_retries=parameters.get("max_retries", 3),
                # Additional fields from server1.py
                routes_to_generate=None,
                filtered_generation_order=None,
                generated_files={},
                files_with_issues=None,
                validation_results=None,
                previous_validation_results=None,
                # Service-specific fields
                fts_modifications=None,
                fts_changes_status=None,
                fts_git_setup_status=None,
                fts_apply_status=None,
                fts_commit_status=None,
                fts_push_status=None,
                fts_branch_name=None,
                fts_git_error=None,
                payouts_modifications=None,
                payouts_changes_status=None,
                payouts_apply_status=None,
                payouts_applied_files=None,
                payouts_git_setup_status=None,
                payouts_branch_name=None,
                payouts_commit_status=None,
                payouts_pr_branch=None,
                payouts_error=None,
                xbalance_modifications=None,
                xbalance_changes_status=None,
                xbalance_apply_status=None,
                xbalance_applied_files=None,
                xbalance_git_setup_status=None,
                xbalance_branch_name=None,
                xbalance_commit_status=None,
                xbalance_pr_branch=None,
                xbalance_error=None,
                # Success criteria
                all_services_completed=False,
                all_prs_created=False,
                pipeline_complete=False
            )
            
            # Execute the workflow
            self.log_behavior(task_id, "Executing LangGraph Workflow", "Running the complete bank integration workflow")
            
            # Handle async workflow execution properly for sync context
            try:
                # Check if we're already in an event loop
                loop = asyncio.get_running_loop()
                # We're in an async context (worker), so we need to run in a new thread with its own loop
                from concurrent.futures import ThreadPoolExecutor
                
                def run_workflow():
                    # Create a new event loop for this thread
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(workflow_graph.ainvoke(initial_state))
                    finally:
                        new_loop.close()
                
                with ThreadPoolExecutor() as executor:
                    future = executor.submit(run_workflow)
                    final_state = future.result()
            except RuntimeError:
                # No running loop, safe to use asyncio.run()
                final_state = asyncio.run(workflow_graph.ainvoke(initial_state))
            
            # Extract results with improved error handling
            workflow_summary = final_state.get("workflow_summary", {})
            current_step = final_state.get("current_step", "unknown")
            
            # Check for successful completion
            workflow_completed_successfully = (
                current_step == "completed" or
                current_step == "complete_workflow" or
                final_state.get("pipeline_complete", False)
            )
            
            if workflow_completed_successfully:
                self.log_behavior(task_id, "LangGraph Workflow Completed", "Bank integration workflow completed successfully")
                return {
                    "success": True,
                    "workflow_type": "langgraph",
                    "bank_name": parameters["bank_name"],
                    "version": parameters["version"],
                    "summary": workflow_summary,
                    "iterations_completed": final_state.get("current_iteration", 0),
                    "services_modified": self._count_successful_services(final_state),
                    "pr_urls": final_state.get("pr_urls", []),
                    "message": "Bank integration completed successfully using LangGraph workflow"
                }
            else:
                # Determine the specific failure reason
                failed_steps = final_state.get("failed_steps", [])
                last_failed_step = failed_steps[-1] if failed_steps else "unknown"
                error_message = f"Workflow failed at step: {last_failed_step}"
                
                self.log_behavior(task_id, "LangGraph Workflow Failed", error_message)
                return {
                    "success": False,
                    "workflow_type": "langgraph",
                    "error": error_message,
                    "failed_steps": failed_steps,
                    "current_step": current_step,
                    "iterations_completed": final_state.get("current_iteration", 0),
                    "summary": workflow_summary,
                    "message": f"Bank integration workflow failed: {error_message}"
                }
                
        except Exception as e:
            self.log_behavior(task_id, "LangGraph Task Failed", f"Exception: {str(e)}")
            self.logger.error(f"Error processing bank integration task {task_id}: {e}")
            return {
                "success": False,
                "error": f"LangGraph workflow execution failed: {str(e)}",
                "workflow_type": "langgraph",
                "message": f"Bank integration task failed with error: {str(e)}"
            }
    
    def log_behavior(self, task_id: str, action: str, description: str) -> None:
        """
        Log agent behavior for a task to create a timeline of actions.
        
        Args:
            task_id: The ID of the task
            action: The action being performed
            description: A description of the action
        """
        timestamp = time.time()
        formatted_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        behavior_entry = {
            "timestamp": timestamp,
            "formatted_time": formatted_time,
            "action": action,
            "description": description
        }
        
        # Create structured directory for logs
        log_dir = os.path.join("tmp", "logs", "workflow-logs")
        os.makedirs(log_dir, exist_ok=True)
        
        # Save the behavior log to a file
        log_file = os.path.join(log_dir, f"task_{task_id}.json")
        try:
            # Check if file exists
            if os.path.exists(log_file):
                with open(log_file, "r") as f:
                    existing_logs = json.load(f)
                existing_logs.append(behavior_entry)
                logs_to_save = existing_logs
            else:
                logs_to_save = [behavior_entry]
            
            # Write updated logs
            with open(log_file, "w") as f:
                json.dump(logs_to_save, f, indent=2)
            logger.debug(f"Saved behavior log for task {task_id}: {action}")
        except Exception as e:
            logger.error(f"Error saving behavior log for task {task_id}: {e}")
    
    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
    
    def _validate_parameters(self, parameters: Dict[str, Any]) -> None:
        """
        Validate required parameters for bank integration.
        
        Args:
            parameters: Parameters to validate
            
        Raises:
            ValueError: If required parameters are missing or invalid
        """
        required_params = ["bank_name"]
        
        for param in required_params:
            if param not in parameters:
                raise ValueError(f"Missing required parameter: {param}")
            
            if not parameters[param]:
                raise ValueError(f"Parameter '{param}' cannot be empty")
        
        # Validate bank name
        bank_name = parameters["bank_name"]
        if not isinstance(bank_name, str) or len(bank_name.strip()) < 2:
            raise ValueError("Bank name must be a non-empty string with at least 2 characters")
        
        # Validate version if provided
        if "version" in parameters:
            version = parameters["version"]
            if not isinstance(version, str) or not version.strip():
                raise ValueError("Version must be a non-empty string")
        
        # Validate max_iterations if provided
        if "max_iterations" in parameters:
            max_iter = parameters["max_iterations"]
            if not isinstance(max_iter, int) or max_iter < 1 or max_iter > 100:
                raise ValueError("max_iterations must be an integer between 1 and 100")
        
        # Validate bank documentation if provided
        if "bank_documentation" in parameters:
            bank_doc = parameters["bank_documentation"]
            if not isinstance(bank_doc, str):
                raise ValueError("Bank documentation must be a string")
            if len(bank_doc) > 5 * 1024 * 1024:  # 5MB limit
                raise ValueError("Bank documentation must be less than 5MB")
        
        # Validate bank documentation filename if provided
        if "bank_doc_filename" in parameters:
            filename = parameters["bank_doc_filename"]
            if not isinstance(filename, str) or not filename.lower().endswith('.md'):
                raise ValueError("Bank documentation filename must be a .md file")
    
    def _prepare_workflow_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare parameters for the LangGraph workflow.
        
        Args:
            parameters: Input parameters from agents catalogue
            
        Returns:
            Parameters formatted for the LangGraph workflow
        """
        workflow_params = {
            "bank_name": parameters["bank_name"].strip(),
            "version": parameters.get("version", "v3"),
            "branch_name": parameters.get("branch_name"),
            "enable_integrations_go": parameters.get("enable_integrations_go", True),
            "enable_fts": parameters.get("enable_fts", True),
            "enable_payouts": parameters.get("enable_payouts", True),
            "enable_xbalance": parameters.get("enable_xbalance", True),
            "enable_terminals": parameters.get("enable_terminals", True),
            "max_iterations": parameters.get("max_iterations", 50),
            "max_retries": parameters.get("max_retries", 3),
            "bank_documentation": parameters.get("bank_documentation"),
            "bank_doc_filename": parameters.get("bank_doc_filename")
        }
        
        return workflow_params
    
    def _get_enabled_services(self, parameters: Dict[str, Any]) -> List[str]:
        """Get list of enabled services from parameters."""
        services = []
        if parameters.get("enable_integrations_go", True):
            services.append("integrations-go")
        if parameters.get("enable_fts", True):
            services.append("fts")
        if parameters.get("enable_payouts", True):
            services.append("payouts")
        if parameters.get("enable_xbalance", True):
            services.append("xbalance")
        if parameters.get("enable_terminals", True):
            services.append("terminals")
        if parameters.get("enable_kube_manifests", True):
            services.append("kube-manifests")
        return services
    
    def _count_successful_services(self, final_state: BankIntegrationState) -> int:
        """Count the number of services that completed successfully."""
        count = 0
        if final_state.get("integrations_go_result", {}).get("success", False):
            count += 1
        if final_state.get("fts_result", {}).get("success", False):
            count += 1
        if final_state.get("payouts_result", {}).get("success", False):
            count += 1
        if final_state.get("xbalance_result", {}).get("success", False):
            count += 1
        if final_state.get("terminals_result", {}).get("success", False):
            count += 1
        if final_state.get("kube_manifests_result", {}).get("success", False):
            count += 1
        return count
    
    def _format_response(self, workflow_result: Dict[str, Any],
                        original_parameters: Dict[str, Any],
                        execution_time: float,
                        task_id: str) -> Dict[str, Any]:
        """
        Format the workflow result for agents catalogue response.
        
        Args:
            workflow_result: Result from the LangGraph workflow
            original_parameters: Original input parameters
            execution_time: Execution time in seconds
            task_id: Task ID
            
        Returns:
            Formatted response for agents catalogue
        """
        success = workflow_result.get("success", False)
        
        if success:
            return {
                "status": "completed",
                "message": f"Successfully integrated {original_parameters['bank_name']} bank across multiple services",
                "workflow_type": "langgraph",
                "task_id": task_id,
                "execution_time": execution_time,
                "bank_name": workflow_result.get("bank_name"),
                "version": workflow_result.get("version"),
                "summary": workflow_result.get("summary", {}),
                "metadata": {
                    "services_modified": workflow_result.get("services_modified", 0),
                    "iterations_completed": workflow_result.get("iterations_completed", 0),
                    "pr_count": len(workflow_result.get("pr_urls", [])),
                    "workflow_completed": True
                },
                "pr_urls": workflow_result.get("pr_urls", []),
                "next_steps": [
                    "Review the created pull requests",
                    "Test the integration in development environment",
                    "Merge PRs after review and testing",
                    "Monitor deployment in staging environment"
                ]
            }
        else:
            return {
                "status": "failed",
                "message": workflow_result.get("error", "Bank integration workflow failed"),
                "workflow_type": "langgraph",
                "task_id": task_id,
                "execution_time": execution_time,
                "error": workflow_result.get("error", "Unknown error"),
                "failed_steps": workflow_result.get("failed_steps", []),
                "current_step": workflow_result.get("current_step", "unknown"),
                "iterations_completed": workflow_result.get("iterations_completed", 0),
                "summary": workflow_result.get("summary", {}),
                "suggestions": [
                    "Check the error details and logs",
                    "Verify bank configuration parameters",
                    "Ensure all required repositories are accessible",
                    "Contact the integration team for assistance"
                ]
            }
    
    # Workflow methods will be implemented in the next part
    def create_bank_integration_graph(self) -> StateGraph:
        """Create the LangGraph workflow for bank integration."""
        # Create the graph
        workflow = StateGraph(BankIntegrationState)
        
        # Add nodes
        workflow.add_node("initialize_workflow", self.initialize_workflow)
        workflow.add_node("run_parallel_integrations", self.run_parallel_integrations)
        workflow.add_node("aggregate_results", self.aggregate_results)
        workflow.add_node("validate_changes", self.validate_changes)
        workflow.add_node("fix_validation_issues", self.fix_validation_issues)
        workflow.add_node("create_prs", self.create_prs)
        workflow.add_node("complete_workflow", self.complete_workflow)
        workflow.add_node("fail_workflow", self.fail_workflow)
        
        # Set entry point
        workflow.set_entry_point("initialize_workflow")
        
        # Add edges
        workflow.add_edge("initialize_workflow", "run_parallel_integrations")
        workflow.add_edge("run_parallel_integrations", "aggregate_results")
        workflow.add_conditional_edges(
            "aggregate_results",
            self.should_continue,
            {
                "validate_changes": "validate_changes",
                "fail_workflow": "fail_workflow"
            }
        )
        workflow.add_conditional_edges(
            "validate_changes",
            self.should_continue,
            {
                "create_prs": "create_prs",
                "fix_validation_issues": "fix_validation_issues",
                "fail_workflow": "fail_workflow"
            }
        )
        workflow.add_conditional_edges(
            "fix_validation_issues",
            self.should_continue,
            {
                "validate_changes": "validate_changes",
                "fail_workflow": "fail_workflow"
            }
        )
        workflow.add_conditional_edges(
            "create_prs",
            self.should_continue,
            {
                "complete_workflow": "complete_workflow",
                "fail_workflow": "fail_workflow"
            }
        )
        workflow.add_edge("complete_workflow", END)
        workflow.add_edge("fail_workflow", END)
        
        return workflow.compile()
    
    # Workflow method implementations
    def initialize_workflow(self, state: BankIntegrationState) -> BankIntegrationState:
        """Initialize the workflow with repositories and configuration."""
        task_id = state["task_id"]
        bank_name = state["bank_name"]
        
        self.log_behavior(task_id, "Workflow Initialization", f"Setting up bank integration for {bank_name}")
        
        # Get enabled repositories
        repositories = BankRepositoryConfig.get_enabled_repositories(
            enable_integrations_go=state["enable_integrations_go"],
            enable_fts=state["enable_fts"],
            enable_payouts=state["enable_payouts"],
            enable_xbalance=state["enable_xbalance"],
            enable_terminals=state["enable_terminals"],
            enable_kube_manifests=state["enable_kube_manifests"]
        )
        
        # Update state
        state["current_step"] = "initialize_workflow"
        state["completed_steps"].append("initialize_workflow")
        state["repositories"] = repositories
        
        # Initialize working branches for each repository
        for repo_name in repositories.keys():
            branch_name = f"feature/{repo_name}-{bank_name.lower()}-{state['version']}-integration-{self._generate_random_suffix()}"
            state["working_branch"][repo_name] = branch_name
        
        # Add initialization message
        state["messages"].append(
            AIMessage(content=f"Initialized bank integration workflow for {bank_name} with {len(repositories)} repositories")
        )
        
        self.logger.info(f"Initialized workflow for {bank_name} with repositories: {list(repositories.keys())}")
        return state
    
    async def run_parallel_integrations(self, state: BankIntegrationState) -> BankIntegrationState:
        """Run parallel integrations across all enabled services using real AI code generation."""
        task_id = state["task_id"]
        bank_name = state["bank_name"]
        version = state["version"]
        
        self.log_behavior(task_id, "Parallel Integration", f"Starting real integrations for {bank_name}")
        
        state["current_step"] = "run_parallel_integrations"
        
        # Create AutonomousAgentTool instances for each enabled service
        integration_tasks = []
        
        if state["enable_integrations_go"]:
            integration_tasks.append(
                self.integrate_integrations_go_service(state)
            )
        
        if state["enable_fts"]:
            integration_tasks.append(
                self.integrate_fts_service(state)
            )
        
        if state["enable_payouts"]:
            integration_tasks.append(
                self.integrate_payouts_service(state)
            )
        
        if state["enable_xbalance"]:
            integration_tasks.append(
                self.integrate_xbalance_service(state)
            )
        
        if state["enable_terminals"]:
            integration_tasks.append(
                self.integrate_terminals_service(state)
            )
        
        if state["enable_kube_manifests"]:
            integration_tasks.append(
                self.integrate_kube_manifests_service(state)
            )
        
        # Run all integrations in parallel using asyncio.gather
        try:
            results = await asyncio.gather(*integration_tasks, return_exceptions=True)
            
            # Process results and update state
            service_names = []
            if state["enable_integrations_go"]: service_names.append("integrations_go")
            if state["enable_fts"]: service_names.append("fts")  
            if state["enable_payouts"]: service_names.append("payouts")
            if state["enable_xbalance"]: service_names.append("xbalance")
            if state["enable_terminals"]: service_names.append("terminals")
            if state["enable_kube_manifests"]: service_names.append("kube_manifests")
            
            for i, result in enumerate(results):
                service = service_names[i]
                
                if isinstance(result, Exception):
                    self.logger.error(f"Integration failed for {service}: {result}")
                    state[f"{service}_result"] = {
                        "success": False, 
                        "error": str(result),
                        "service": service
                    }
                    state["failed_steps"].append(f"integrate_{service}")
                else:
                    self.logger.info(f"Integration successful for {service}")
                    state[f"{service}_result"] = result
            
        except Exception as e:
            self.logger.error(f"Parallel integration failed: {e}")
            state["error_messages"].append(f"Parallel integration error: {str(e)}")
        
        state["completed_steps"].append("run_parallel_integrations")
        return state
    
    async def integrate_xbalance_service(self, state: BankIntegrationState) -> Dict[str, Any]:
        """Integrate X-Balance service with real AI code generation and job files."""
        task_id = state["task_id"]
        bank_name = state["bank_name"]
        version = state["version"]
        branch_name = state["working_branch"].get("x-balances", f"feature/xbalance-{bank_name.lower()}-integration")
        
        self.logger.info(f"Starting X-Balance integration for {bank_name}")
        
        try:
            # Create AutonomousAgentTool for X-Balance repository
            agent_tool = AutonomousAgentTool()
            
            # Define the integration prompt (based on server1.py logic)
            xbalance_prompt = f"""
You are a Go developer working on X-Balance service integration for {bank_name.upper()} bank.

TASK: Generate Go code files for X-Balance service bank integration

BANK DETAILS:
- Bank Name: {bank_name.upper()}
- Version: {version}
- Target Directory: x-balances/internal/job/balanceFetch/{bank_name.lower()}/

REQUIRED FILES TO GENERATE:
1. balance_fetch.go - Main job implementation following worker.Job pattern
2. balance_fetch_test.go - Unit tests for the job

REFERENCE PATTERN (Use this exact structure):
{self._get_xbalance_job_reference()}

MODIFICATIONS NEEDED:
1. Replace BANKNAME with {bank_name.lower()} 
2. Replace BANKUPPER with {bank_name.upper()}
3. Update queue names and job configuration
4. Implement proper error handling and logging
5. Follow the exact import structure shown in reference

CONFIGURATION FILE UPDATES:
1. Add rate limiter configuration to x-balances/internal/constant/constant.go:
   ```go
   "{bank_name.lower()}": getMutexBasedTokenBucketRateLimiter(5, time.Second),
   ```

2. Add log constant to x-balances/pkg/log/code.go:
   ```go
   {bank_name.upper()}FetchBalanceWorkerTimeTaken = "fetch_balance_worker_time_taken"
   ```

Generate all required files and configuration updates for {bank_name.upper()} bank integration.
"""

            # Setup Git authentication before integration
            auth_setup = await self._setup_git_authentication(BankRepositoryConfig.X_BALANCE)
            if not auth_setup.get("success"):
                self.logger.error(f"Git authentication setup failed: {auth_setup.get('error')}")
                return {
                    "success": False,
                    "service": "x-balances", 
                    "bank_name": bank_name,
                    "error": f"Git authentication failed: {auth_setup.get('error')}",
                    "branch_name": branch_name
                }
            
            # Use AutonomousAgentTool to perform the integration
            integration_result = await agent_tool.run_autonomous_task(
                repository_url=BankRepositoryConfig.X_BALANCE,
                branch_name=branch_name,
                task_description=f"Integrate {bank_name.upper()} bank into X-Balance service",
                prompt=xbalance_prompt,
                max_iterations=state.get("max_iterations", 50)
            )
            
            if integration_result.get("success"):
                # Extract PR URL and other details
                pr_url = integration_result.get("pr_url")
                files_created = integration_result.get("files_modified", [])
                
                self.logger.info(f"X-Balance integration successful for {bank_name}, PR: {pr_url}")
                
                return {
                    "success": True,
                    "service": "x-balances",
                    "bank_name": bank_name,
                    "pr_url": pr_url,
                    "files_created": files_created,
                    "branch_name": branch_name,
                    "integration_type": "job_implementation"
                }
            else:
                error_msg = integration_result.get("error", "Unknown error")
                self.logger.error(f"X-Balance integration failed for {bank_name}: {error_msg}")
                
                return {
                    "success": False,
                    "service": "x-balances", 
                    "bank_name": bank_name,
                    "error": error_msg,
                    "branch_name": branch_name
                }
                
        except Exception as e:
            self.logger.error(f"X-Balance integration exception for {bank_name}: {e}")
            return {
                "success": False,
                "service": "x-balances",
                "bank_name": bank_name, 
                "error": str(e),
                "branch_name": branch_name
            }
    
    def _get_xbalance_job_reference(self) -> str:
        """Get the X-Balance job reference pattern from the reference file."""
        try:
            # Read the reference file content (same as server1.py)
            reference_path = "/Users/deepak.yadav/Downloads/INT-GO_LANGGRAPH/xbalance_job_reference.txt"
            with open(reference_path, "r") as f:
                return f.read()
        except Exception as e:
            self.logger.warning(f"Could not read X-Balance reference file: {e}")
            # Return a basic pattern if reference file is not available
            return """
REFERENCE PATTERN:
Create balance_fetch.go and balance_fetch_test.go files following the worker.Job pattern.
Include proper imports, job configuration, and error handling.
"""
    
    async def integrate_fts_service(self, state: BankIntegrationState) -> Dict[str, Any]:
        """Integrate FTS (Fund Transfer Service) with AI code generation."""
        task_id = state["task_id"]
        bank_name = state["bank_name"]
        version = state["version"]
        branch_name = state["working_branch"].get("fts", f"feature/fts-{bank_name.lower()}-{version}-integration")
        
        self.logger.info(f"Starting FTS integration for {bank_name}")
        
        try:
            agent_tool = AutonomousAgentTool()
            
            # Load FTS reference files for detailed context
            fts_references = self._load_fts_references()
            
            fts_prompt = f"""
You are a Go developer working on FTS (Fund Transfer Service) integration for {bank_name.upper()} bank.

🛑 **IMMEDIATE TASK - DO THIS FIRST** 🛑

**YOUR FIRST ACTION MUST BE:**
1. Clone the repository: `gh repo clone razorpay/fts`
2. Navigate to FTS directory  
3. **IMMEDIATELY** edit these 2 critical files:
   - `internal/transfer/attempt_processor.go` (add {bank_name.upper()} routing)
   - `internal/transfer/transfer_mode_processor.go` (add {bank_name.upper()} modes)

🚨 **INTEGRATION WILL FAIL COMPLETELY WITHOUT THESE 2 CORE FILES** 🚨

**THESE FILES CONTAIN THE ROUTING LOGIC THAT DISPATCHES REQUESTS TO YOUR BANK.**
**WITHOUT MODIFYING THEM, NO REQUESTS WILL REACH {bank_name.upper()} - THE INTEGRATION IS BROKEN.**

⛔ **YOU CANNOT CREATE BANK IMPLEMENTATION FILES UNTIL CORE ROUTING IS FIXED** ⛔

### 🔥 **MANDATORY SEQUENCE - NO SKIPPING:**

**STEP 1**: Edit `internal/transfer/attempt_processor.go`
- Find `getTaskNameForDispatchTransfer()` function
- Add `case channel.{bank_name.upper()}:` section (copy IDFC pattern)
- Find `dispatchForStatusCheck()` function  
- Add `if processor.attempt.Channel == channel.{bank_name.upper()}` section
- **VERIFY**: Run `grep "{bank_name.upper()}" internal/transfer/attempt_processor.go`

**STEP 2**: Edit `internal/transfer/transfer_mode_processor.go`
- Add `{bank_name.upper()} []string` to AllowedModes struct
- Add `case "{bank_name.upper()}":` in getModeAndChannelByShortCode()
- Add `case "{bank_name.upper()}":` in setMode()
- **VERIFY**: Run `grep "{bank_name.upper()}" internal/transfer/transfer_mode_processor.go`

⚠️ **CHECKPOINT: If either grep shows NO results, STOP and fix before continuing.**

BANK CONFIGURATION:
- Bank Name: {bank_name.upper()}
- Bank Short Code: {bank_name[:4].upper()}B  
- Version: {version}
- Supported Payment Modes: UPI, IMPS, NEFT, RTGS, IFT

KEY INTEGRATION POINTS FROM REFERENCE PATTERNS:

## 1. ENV.DEFAULT.TOML CONFIGURATION
{fts_references.get('env_config', 'Reference pattern not available')}

## 2. CHANNEL.GO MODIFICATIONS  
{fts_references.get('channel', 'Reference pattern not available')}

## 3. CONFIG/CHANNEL.GO MODIFICATIONS
{fts_references.get('config_channel', 'Reference pattern not available')}

## 4. ATTEMPT PROCESSOR MODIFICATIONS (USE THESE EXACT PATTERNS)
{fts_references.get('attempt_processor', 'Reference pattern not available')}

**⚡ COPY-PASTE INSTRUCTION FOR ATTEMPT_PROCESSOR.GO:**
Find existing IDFC cases in the file and add IDENTICAL {bank_name.upper()} cases.
Replace every "IDFC" with "{bank_name.upper()}" and "idfc" with "{bank_name.lower()}".

## 5. TRANSFER MODE PROCESSOR MODIFICATIONS (USE THESE EXACT PATTERNS)  
{fts_references.get('transfer_mode_processor', 'Reference pattern not available')}

**⚡ COPY-PASTE INSTRUCTION FOR TRANSFER_MODE_PROCESSOR.GO:**
Find existing IDFC entries in the file and add IDENTICAL {bank_name.upper()} entries.
Replace every "IDFC" with "{bank_name.upper()}" and "idfc" with "{bank_name.lower()}".

## CUSTOM FTS INTEGRATION GUIDELINES
{fts_references.get('custom_prompt', 'Custom prompt not available')}

IMPLEMENTATION REQUIREMENTS:

### Repository Setup - RESILIENT DIRECTORY NAVIGATION

{self._get_git_workflow_instructions(
    repository_name="fts",
    bank_name=bank_name,
    service_name="FTS",
    commit_details=f"""- Add {bank_name.upper()} bank routing to attempt_processor.go and transfer_mode_processor.go
- Create {bank_name}/{version}/ directory with complete bank implementation:
  * constants.go - Bank constants and configurations
  * error_code.go - Error code definitions  
  * gateway_model.go - Data structures and models
  * base.go - Base functionality and core logic
  * gateway_error_mapper.go - Error mapping utilities
  * action_store.go - Action routing logic
- Update env.default.toml with {bank_name.upper()} configuration sections
- Support for all transfer modes and payment channels""",
    pr_body=f"""## Summary
This PR integrates {bank_name.upper()} bank into the FTS (Fund Transfer Service), adding comprehensive transfer capabilities.

## Changes Made
- **Updated**: internal/transfer/attempt_processor.go with {bank_name.upper()} routing logic
- **Updated**: internal/transfer/transfer_mode_processor.go with {bank_name.upper()} transfer modes
- **Created**: fts/{bank_name}/{version}/ directory with complete bank implementation
- **Updated**: env.default.toml with {bank_name.upper()} specific configuration
- **Support**: All transfer modes (UPI, IMPS, NEFT, RTGS) and error handling

## Verification
- ✅ Core routing logic updated for {bank_name.upper()} bank
- ✅ Transfer mode processing configured correctly
- ✅ Complete bank implementation created with all required files
- ✅ Configuration sections added and validated
- ✅ Error mapping and action routing implemented

🤖 Generated with [Claude Code](https://claude.com/claude-code)"""
)}

**DIRECTORY NAVIGATION RULES:**
1. **ALWAYS verify directory**: Use `pwd` after `cd` commands
2. **Use absolute paths**: Never rely on relative paths in commands
3. **Set environment variables**: Use `export SHELL_PWD="<absolute_path>"` pattern
4. **Include fallback patterns**: If `cd` fails, try `cd "$SHELL_PWD"` 
5. **Use unique branch names**: Add timestamp to avoid conflicts
6. **Test directory existence**: Use `ls -la` to verify before proceeding

**COMMAND PATTERNS:**
```bash
# Safe file operations - always use absolute paths
ls -la "$SHELL_PWD/internal/transfer/"
cat "$SHELL_PWD/internal/channel/channel.go"
grep -r "IDFC" "$SHELL_PWD/internal/"
```

**IF DIRECTORY ISSUES PERSIST:**
- Use `find` commands from workspace root: `find . -name "channel.go" -path "*/internal/channel/*"`
- Use full paths in all commands: `/tmp/workspace-xxx/fts/internal/transfer/attempt_processor.go`
- Verify file existence before editing: `test -f "$SHELL_PWD/internal/channel/channel.go" && echo "Found"`

### Files to Create/Modify

**CRITICAL: These existing files MUST be modified first (integration will fail without them):**

1. **internal/transfer/attempt_processor.go** - MANDATORY: Add {bank_name.upper()} case to getTaskNameForDispatchTransfer() and dispatchForStatusCheck() functions
2. **internal/transfer/transfer_mode_processor.go** - MANDATORY: Add {bank_name.upper()} to AllowedModes struct, getModeAndChannelByShortCode(), and setMode() functions
3. **internal/channel/channel.go** - MANDATORY: Add {bank_name.upper()} constant, channels array, allowed modes mapping, GetApiConfig case
4. **internal/config/channel.go** - MANDATORY: Add {bank_name.upper()} field to Channels struct with TOML binding

**Additional required files:**

5. **config/env.default.toml** - Add {bank_name.upper()} worker mappings and task configurations  
6. **{bank_name.lower()}/{version}/constants.go** - Bank-specific constants
7. **{bank_name.lower()}/{version}/error_code.go** - Error definitions
8. **{bank_name.lower()}/{version}/gateway_model.go** - Data structures
9. **{bank_name.lower()}/{version}/base.go** - Base functionality
10. **{bank_name.lower()}/{version}/gateway_error_mapper.go** - Error mapping
11. **{bank_name.lower()}/{version}/action_store.go** - Action routing

**CRITICAL REQUIREMENT**: You MUST modify the existing core files (items 1-4) or the integration will not function. These are not optional - they contain the routing logic that dispatches requests to your bank.

### 🔒 MANDATORY EXECUTION ORDER (BLOCKING STEPS):

**PHASE 1: CORE ROUTING FILES (CANNOT BE SKIPPED)**
1. ✅ **STEP 1A**: Edit `internal/transfer/attempt_processor.go` - Add {bank_name.upper()} cases
   - Add case in `getTaskNameForDispatchTransfer()` 
   - Add case in `dispatchForStatusCheck()`
   - **VERIFY**: Run `grep -n "{bank_name.upper()}" internal/transfer/attempt_processor.go`
   
2. ✅ **STEP 1B**: Edit `internal/transfer/transfer_mode_processor.go` - Add {bank_name.upper()} logic  
   - Add {bank_name.upper()} to AllowedModes struct
   - Add {bank_name.upper()} case in getModeAndChannelByShortCode()
   - Add {bank_name.upper()} case in setMode()
   - **VERIFY**: Run `grep -n "{bank_name.upper()}" internal/transfer/transfer_mode_processor.go`

⛔ **CHECKPOINT**: If grep commands above show NO results, STOP and fix the files. Do not continue.

**PHASE 2: CONFIGURATION FILES (AFTER PHASE 1 ONLY)**
3. **STEP 2A**: Edit `internal/channel/channel.go` - Add channel constants
4. **STEP 2B**: Edit `internal/config/channel.go` - Add struct fields  

**PHASE 3: BANK IMPLEMENTATION (AFTER PHASES 1-2 ONLY)**
5. **STEP 3A**: Create bank-specific directory and files
6. **STEP 3B**: Update TOML configuration

### Critical Implementation Notes:
- Replace "IDFC" with "{bank_name.upper()}" and "idfc" with "{bank_name.lower()}" throughout
- Replace "IDFB" with "{bank_name[:4].upper()}B" for short code mapping
- Support all payment modes: UPI, IMPS, NEFT, RTGS, IFT
- Include high volume UPI handling
- Support payroll account routing
- Add direct account vs regular account segregation
- Follow exact IDFC patterns for consistency

⚠️ **FINAL VERIFICATION (MANDATORY BEFORE COMMIT):**
Run these commands to verify integration will work:
```bash
grep -n "{bank_name.upper()}" internal/transfer/attempt_processor.go
grep -n "{bank_name.upper()}" internal/transfer/transfer_mode_processor.go  
grep -n "{bank_name.upper()}" internal/channel/channel.go
grep -n "{bank_name.upper()}" internal/config/channel.go
```

**If ANY grep command shows NO results, the integration is BROKEN and MUST be fixed.**

🚨 **CONSEQUENCES OF SKIPPING CORE FILES:**
- Requests to {bank_name.upper()} will return "channel not found" errors
- No transactions will process for {bank_name.upper()}
- The entire integration is useless regardless of other files
- Production deployment will fail validation

### EFFICIENCY GUIDELINES:
1. **Time Limits**: Don't spend >3 minutes on directory navigation - use absolute paths immediately
2. **Quick Verification**: Use `ls -la <path>` to verify directories exist before complex operations
3. **Pattern Recognition**: If same directory command fails twice, switch to absolute path method
4. **Progressive Fallback**: Try basic `cd`, then `SHELL_PWD` pattern, then absolute paths
5. **Early Detection**: If shell environment has issues, set all paths as variables upfront

**CRITICAL**: Execute step by step in the EXACT order specified. DO NOT skip any MANDATORY steps.

{self._get_dynamic_git_authentication_instructions()}"""

            # Setup Git authentication before integration
            auth_setup = await self._setup_git_authentication(BankRepositoryConfig.FTS)
            if not auth_setup.get("success"):
                self.logger.error(f"Git authentication setup failed: {auth_setup.get('error')}")
                return {
                    "success": False,
                    "service": "fts", 
                    "bank_name": bank_name,
                    "error": f"Git authentication failed: {auth_setup.get('error')}",
                    "branch_name": branch_name
                }

            integration_result = await agent_tool.run_autonomous_task(
                repository_url=BankRepositoryConfig.FTS,
                branch_name=branch_name,
                task_description=f"Integrate {bank_name.upper()} bank into FTS",
                prompt=fts_prompt,
                max_iterations=state.get("max_iterations", 50)
            )
            
            if integration_result.get("success"):
                return {
                    "success": True,
                    "service": "fts",
                    "bank_name": bank_name,
                    "pr_url": integration_result.get("pr_url"),
                    "files_created": integration_result.get("files_modified", []),
                    "branch_name": branch_name,
                    "integration_type": "batch_generation"
                }
            else:
                return {
                    "success": False,
                    "service": "fts",
                    "bank_name": bank_name,
                    "error": integration_result.get("error", "Unknown error"),
                    "branch_name": branch_name
                }
                
        except Exception as e:
            self.logger.error(f"FTS integration exception for {bank_name}: {e}")
            return {
                "success": False,
                "service": "fts",
                "bank_name": bank_name,
                "error": str(e),
                "branch_name": branch_name
            }
    
    async def integrate_payouts_service(self, state: BankIntegrationState) -> Dict[str, Any]:
        """Integrate Payouts service with AI code generation."""
        task_id = state["task_id"]
        bank_name = state["bank_name"]
        version = state["version"]
        branch_name = state["working_branch"].get("payouts", f"feature/payouts-{bank_name.lower()}-integration")
        
        self.logger.info(f"Starting Payouts integration for {bank_name}")
        
        try:
            agent_tool = AutonomousAgentTool()
            
            payouts_prompt = f"""
You are a Go developer working on Payouts service integration for {bank_name.upper()} bank.

TASK: Generate Go code files for Payouts bank integration

BANK DETAILS:
- Bank Name: {bank_name.upper()}
- Version: {version}

REQUIRED FILES:
1. Bank-specific payout implementations
2. Model definitions for payout requests/responses
3. Configuration updates
4. Test files

Generate all required files for {bank_name.upper()} bank integration following existing patterns.
"""

            # Setup Git authentication before integration
            auth_setup = await self._setup_git_authentication(BankRepositoryConfig.PAYOUTS)
            if not auth_setup.get("success"):
                self.logger.error(f"Git authentication setup failed: {auth_setup.get('error')}")
                return {
                    "success": False,
                    "service": "payouts", 
                    "bank_name": bank_name,
                    "error": f"Git authentication failed: {auth_setup.get('error')}",
                    "branch_name": branch_name
                }

            integration_result = await agent_tool.run_autonomous_task(
                repository_url=BankRepositoryConfig.PAYOUTS,
                branch_name=branch_name,
                task_description=f"Integrate {bank_name.upper()} bank into Payouts service",
                prompt=payouts_prompt,
                max_iterations=state.get("max_iterations", 50)
            )
            
            if integration_result.get("success"):
                return {
                    "success": True,
                    "service": "payouts",
                    "bank_name": bank_name,
                    "pr_url": integration_result.get("pr_url"),
                    "files_created": integration_result.get("files_modified", []),
                    "branch_name": branch_name,
                    "integration_type": "payout_implementation"
                }
            else:
                return {
                    "success": False,
                    "service": "payouts",
                    "bank_name": bank_name,
                    "error": integration_result.get("error", "Unknown error"),
                    "branch_name": branch_name
                }
                
        except Exception as e:
            self.logger.error(f"Payouts integration exception for {bank_name}: {e}")
            return {
                "success": False,
                "service": "payouts",
                "bank_name": bank_name,
                "error": str(e),
                "branch_name": branch_name
            }
    
    async def integrate_integrations_go_service(self, state: BankIntegrationState) -> Dict[str, Any]:
        """Integrate Integrations-Go service with AI code generation."""
        task_id = state["task_id"]
        bank_name = state["bank_name"]
        version = state["version"]
        branch_name = state["working_branch"].get("integrations-go", f"feature/integrations-go-{bank_name.lower()}-integration")
        
        self.logger.info(f"Starting Integrations-Go integration for {bank_name}")
        
        try:
            agent_tool = AutonomousAgentTool()
            
            integrations_go_prompt = f"""
You are a Go developer working on Integrations-Go service integration for {bank_name.upper()} bank.

TASK: Generate Go code files for Integrations-Go bank integration

BANK DETAILS:
- Bank Name: {bank_name.upper()}
- Version: {version}

REQUIRED FILES:
1. Gateway implementations for payment processing
2. Model definitions
3. Configuration updates
4. Integration tests

Generate all required files for {bank_name.upper()} bank integration following existing gateway patterns.
"""

            # Setup Git authentication before integration
            auth_setup = await self._setup_git_authentication(BankRepositoryConfig.INTEGRATIONS_GO)
            if not auth_setup.get("success"):
                self.logger.error(f"Git authentication setup failed: {auth_setup.get('error')}")
                return {
                    "success": False,
                    "service": "integrations-go", 
                    "bank_name": bank_name,
                    "error": f"Git authentication failed: {auth_setup.get('error')}",
                    "branch_name": branch_name
                }

            integration_result = await agent_tool.run_autonomous_task(
                repository_url=BankRepositoryConfig.INTEGRATIONS_GO,
                branch_name=branch_name,
                task_description=f"Integrate {bank_name.upper()} bank into Integrations-Go",
                prompt=integrations_go_prompt,
                max_iterations=state.get("max_iterations", 50)
            )
            
            if integration_result.get("success"):
                return {
                    "success": True,
                    "service": "integrations-go",
                    "bank_name": bank_name,
                    "pr_url": integration_result.get("pr_url"),
                    "files_created": integration_result.get("files_modified", []),
                    "branch_name": branch_name,
                    "integration_type": "gateway_implementation"
                }
            else:
                return {
                    "success": False,
                    "service": "integrations-go",
                    "bank_name": bank_name,
                    "error": integration_result.get("error", "Unknown error"),
                    "branch_name": branch_name
                }
                
        except Exception as e:
            self.logger.error(f"Integrations-Go integration exception for {bank_name}: {e}")
            return {
                "success": False,
                "service": "integrations-go",
                "bank_name": bank_name,
                "error": str(e),
                "branch_name": branch_name
                }

    async def integrate_terminals_service(self, state: BankIntegrationState) -> Dict[str, Any]:
        """Integrate Terminals service with AI code generation."""
        task_id = state["task_id"]
        bank_name = state["bank_name"]
        version = state["version"]
        bank_upper = bank_name.upper()
        branch_name = state["working_branch"].get("terminals", f"feature/terminals-{bank_name.lower()}-integration")
        
        self.logger.info(f"Starting Terminals integration for {bank_name}")
        
        try:
            agent_tool = AutonomousAgentTool()
            
            # Get enhanced terminals prompt with reference patterns
            terminals_prompt = self._get_terminals_service_prompt(bank_name, bank_upper, version)
            
            # Git authentication handled automatically by Docker environment

            integration_result = await agent_tool.run_autonomous_task(
                repository_url=BankRepositoryConfig.TERMINALS,
                branch_name=branch_name,
                task_description=f"Integrate {bank_upper} bank into Terminals service",
                prompt=terminals_prompt,
                max_iterations=state.get("max_iterations", 50)
            )
            
            if integration_result.get("success"):
                return {
                    "success": True,
                    "service": "terminals",
                    "bank_name": bank_name,
                    "pr_url": integration_result.get("pr_url"),
                    "files_created": integration_result.get("files_modified", []),
                    "branch_name": branch_name,
                    "integration_type": "gateway_constants_validation"
                }
            else:
                return {
                    "success": False,
                    "service": "terminals",
                    "bank_name": bank_name,
                    "error": integration_result.get("error", "Unknown error"),
                    "branch_name": branch_name
                }
                
        except Exception as e:
            self.logger.error(f"Terminals integration exception for {bank_name}: {e}")
            return {
                "success": False,
                "service": "terminals",
                "bank_name": bank_name,
                "error": str(e),
                "branch_name": branch_name
            }
    
    def aggregate_results(self, state: BankIntegrationState) -> BankIntegrationState:
        """Aggregate results from all service integrations."""
        task_id = state["task_id"]
        
        self.log_behavior(task_id, "Aggregating Results", "Collecting results from all service integrations")
        
        # Collect all results
        all_results = {}
        if state["enable_integrations_go"]:
            all_results["integrations-go"] = state.get("integrations_go_result", {})
        if state["enable_fts"]:
            all_results["fts"] = state.get("fts_result", {})
        if state["enable_payouts"]:
            all_results["payouts"] = state.get("payouts_result", {})
        if state["enable_xbalance"]:
            all_results["xbalance"] = state.get("xbalance_result", {})
        if state["enable_terminals"]:
            all_results["terminals"] = state.get("terminals_result", {})
        if state["enable_kube_manifests"]:
            all_results["kube-manifests"] = state.get("kube_manifests_result", {})
        
        # Count successful integrations
        successful_integrations = sum(1 for result in all_results.values()
                                    if result.get("success", False))
        
        # Collect PR URLs
        pr_urls = []
        for result in all_results.values():
            if result.get("pr_url"):
                pr_urls.append(result["pr_url"])
        
        state["pr_urls"] = pr_urls
        
        # Update workflow summary
        state["workflow_summary"] = {
            "total_services": len(all_results),
            "successful_integrations": successful_integrations,
            "failed_integrations": len(all_results) - successful_integrations,
            "pr_count": len(pr_urls),
            "results": all_results
        }
        
        state["current_step"] = "aggregate_results"
        state["completed_steps"].append("aggregate_results")
        
        return state
    
    def should_continue(self, state: BankIntegrationState) -> str:
        """Determine the next step in the workflow based on current state."""
        current_step = state.get("current_step", "")
        failed_steps = state.get("failed_steps", [])
        current_iteration = state.get("current_iteration", 0)
        max_iterations = state.get("max_iterations", 50)
        
        # Check if we've exceeded max iterations
        if current_iteration >= max_iterations:
            return "fail_workflow"
        
        # Handle different workflow states
        if current_step == "aggregate_results":
            # Check if we have at least one successful integration
            successful_count = self._count_successful_services(state)
            if successful_count > 0:
                return "validate_changes"
            else:
                return "fail_workflow"
        
        elif current_step == "validate_changes":
            validation_result = state.get("validation_result", {})
            if validation_result.get("success", False):
                return "create_prs"
            elif len(failed_steps) > 5:  # Too many failures
                return "fail_workflow"
            else:
                return "fix_validation_issues"
        
        elif current_step == "fix_validation_issues":
            if len(failed_steps) > 10:  # Too many failures
                return "fail_workflow"
            else:
                return "validate_changes"
        
        elif current_step == "create_prs":
            if state.get("all_prs_created", False):
                return "complete_workflow"
            else:
                return "fail_workflow"
        
        # Default fallback
        return "fail_workflow"
    
    def validate_changes(self, state: BankIntegrationState) -> BankIntegrationState:
        """Validate all changes made during integration."""
        task_id = state["task_id"]
        
        self.log_behavior(task_id, "Validating Changes", "Validating all service integrations")
        
        # Simple validation - check if we have successful results
        successful_results = self._count_successful_services(state)
        total_results = len([s for s in ["integrations-go", "fts", "payouts", "xbalance"] 
                            if state.get(f"enable_{s.replace('-', '_')}", True)])
        
        # Consider validation successful if at least 80% of integrations succeeded
        validation_success = (successful_results / total_results) >= 0.8 if total_results > 0 else False
        
        state["validation_result"] = {
            "success": validation_success,
            "successful_results": successful_results,
            "total_results": total_results,
            "success_rate": (successful_results / total_results) if total_results > 0 else 0
        }
        
        state["current_step"] = "validate_changes"
        state["completed_steps"].append("validate_changes")
        
        if not validation_success:
            state["failed_steps"].append("validate_changes")
        
        return state
    
    def fix_validation_issues(self, state: BankIntegrationState) -> BankIntegrationState:
        """Fix validation issues found during validation."""
        task_id = state["task_id"]
        
        self.log_behavior(task_id, "Fixing Validation Issues", "Attempting to fix validation issues")
        
        # Increment iteration counter
        state["current_iteration"] += 1
        
        state["current_step"] = "fix_validation_issues"
        state["completed_steps"].append("fix_validation_issues")
        
        return state
    
    def create_prs(self, state: BankIntegrationState) -> BankIntegrationState:
        """Create pull requests for all successful integrations."""
        task_id = state["task_id"]
        
        self.log_behavior(task_id, "Creating Pull Requests", "Creating PRs for all successful integrations")
        
        # Check if we already have PRs from the integration steps
        existing_prs = len(state.get("pr_urls", []))
        
        # Mark PRs as created if we have them
        state["all_prs_created"] = existing_prs > 0
        
        state["current_step"] = "create_prs"
        state["completed_steps"].append("create_prs")
        
        return state
    
    def complete_workflow(self, state: BankIntegrationState) -> BankIntegrationState:
        """Complete the workflow successfully."""
        task_id = state["task_id"]
        bank_name = state["bank_name"]
        
        self.log_behavior(task_id, "Workflow Completed", f"Bank integration workflow completed successfully for {bank_name}")
        
        # Mark as completed
        state["current_step"] = "completed"
        state["completed_steps"].append("complete_workflow")
        state["pipeline_complete"] = True
        
        return state
    
    def fail_workflow(self, state: BankIntegrationState) -> BankIntegrationState:
        """Fail the workflow due to errors."""
        task_id = state["task_id"]
        bank_name = state["bank_name"]
        
        self.log_behavior(task_id, "Workflow Failed", f"Bank integration workflow failed for {bank_name}")
        
        state["current_step"] = "failed"
        state["failed_steps"].append("fail_workflow")
        
        return state
    
    def _get_xbalance_service_prompt(self, bank_name: str, bank_upper: str, version: str) -> str:
        """Generate comprehensive prompt for X-Balance service integration with all reference patterns."""
        
        # Load X-Balance reference files
        reference_files = self._load_xbalance_references()
        
        return f"""# Bank Integration Task: {bank_upper} Bank X-Balance Service

You need to integrate {bank_upper} bank into the X-Balance service following EXACT patterns from reference implementations.

## REFERENCE PATTERNS (FOLLOW EXACTLY):

### JOB REFERENCE PATTERN:
{reference_files['job']}

### CHANNEL REFERENCE PATTERN:
{reference_files['channel']}

### RATE LIMITER REFERENCE PATTERN:
{reference_files['ratelimiter']}

### TRANSFORMER REFERENCE PATTERN:
{reference_files['transformer']}

### FACTORY REFERENCE PATTERN:
{reference_files['factory']}

### WORKER REGISTRATION PATTERN:
{reference_files['worker']}

### SERVICE OVERVIEW:
{reference_files['service_overview']}

END OF REFERENCE PATTERNS

## INTEGRATION TASK FOR {bank_upper} BANK:

TARGET BANK: {bank_upper} ({bank_name})
RATE LIMIT: 16 requests (async) - use standard limit
TIMEOUT: 60 seconds
QUEUE PATTERN: {{env}}-x-balances-{bank_name}-balance-update-live

## REQUIRED INTEGRATIONS (follow reference patterns exactly):

**MODIFICATION: x-balances/internal/enum/channel/channel.go**
```go
// Add to constants section (after existing banks like YESBANK, IDFC)
// {bank_upper} bank as channel
{bank_upper} 

// Add to toString map
{bank_upper}: "{bank_name}",

// Add to fromString map  
"{bank_name}": {bank_upper},
```

**CREATE_DIRECTORY: x-balances/internal/transformer/mozart/{bank_name}/models**

**CREATE_FILE: x-balances/internal/transformer/mozart/{bank_name}/{bank_name}_transformer.go**
```go
// Follow the EXACT transformer pattern from reference
// Replace all BANKNAME with {bank_name} and BANKNAME_UPPER with {bank_upper}
// Implement MozartTransformer interface
// Include proper validation and error handling
```

**CREATE_FILE: x-balances/internal/transformer/mozart/{bank_name}/models/request.go**
```go
// Bank-specific request models following reference pattern
```

**CREATE_FILE: x-balances/internal/transformer/mozart/{bank_name}/models/response.go**
```go
// Bank-specific response models following reference pattern
```

**CREATE_FILE: x-balances/internal/transformer/mozart/{bank_name}/{bank_name}_transformer_test.go**
```go
// Comprehensive unit tests following reference pattern
```

**MODIFICATION: x-balances/internal/transformer/mozart/factory/transformer.go**
```go
// Add import for {bank_name} package
import "github.com/razorpay/x-balances/internal/transformer/mozart/{bank_name}"

// Add case in GetTransformer switch
case "{bank_name}":
	return &{bank_name}.{bank_name.title()}Transformer{{}}
```

**MODIFICATION: x-balances/internal/constant/constant.go**
```go
// Add rate limiter configuration following EXACT pattern with tab indentation
"{bank_name}": {{
	"async": getMutexBasedTokenBucketRateLimiter(16, "{bank_name}", "async", store),
}},
```

**CREATE_DIRECTORY: x-balances/internal/job/balanceFetch/{bank_name}**

**CREATE_FILE: x-balances/internal/job/balanceFetch/{bank_name}/balance_fetch.go**
```go
// Follow the EXACT pattern from JOB REFERENCE above
// Replace all BANKNAME with {bank_name} and BANKNAME_UPPER with {bank_upper}
// Use worker.Job pattern, Handle() method, correct imports as shown in reference
// Queue name: fmt.Sprintf("%s-x-balances-{bank_name}-balance-update-live", env.New())
// Worker name: "balance_fetch_{bank_name}_worker"
// Include metrics: metrics.Core().GatewayBalanceFetchLatencyUpdate("false", "{bank_upper}", float64(duration))
// Log constant: pkglog.{bank_upper}FetchBalanceWorkerTimeTaken
```

**CREATE_FILE: x-balances/internal/job/balanceFetch/{bank_name}/balance_fetch_test.go**
```go
// Follow reference pattern for comprehensive unit tests
// Test scenarios: successful balance fetch, empty merchant ID, service error
// Use gomock for mocking with proper setup and assertions
// Include TestRegisterHandler function
```

**MODIFICATION: x-balances/cmd/worker/main.go**
```go
// Add import
import "{bank_name}Job" "github.com/razorpay/x-balances/internal/job/balanceFetch/{bank_name}"

// Add initialization call (in appropriate section)
{bank_name}Job.Initialise()

// Add handler registration
{bank_name}Job.RegisterHandler(balanceFetchService)
```

**MODIFICATION: x-balances/pkg/log/code.go**
```go
// Add ONLY the new log constant for {bank_upper} (do not include existing constants):
//{bank_upper}FetchBalanceWorkerTimeTaken is used to log time taken by fetch balance worker
{bank_upper}FetchBalanceWorkerTimeTaken = "{bank_upper}_FETCH_BALANCE_WORKER_TIME_TAKEN"
```

**MODIFICATION: x-balances/cmd/server/main.go**
```go
// Add import and registration if needed for server mode
import "{bank_name}Job" "github.com/razorpay/x-balances/internal/job/balanceFetch/{bank_name}"
// Add calls as needed
```

## CRITICAL REQUIREMENTS:
1. Use TAB indentation throughout (not spaces) - Go standard
2. Follow EXACT patterns from reference files above
3. Replace template values: BANKNAME→{bank_name}, BANKNAME_UPPER→{bank_upper}
4. Use standard rate limit: 16 requests for async operations
5. Queue naming: {{env}}-x-balances-{bank_name}-balance-update-live
6. Worker name: balance_fetch_{bank_name}_worker
7. Proper error handling with structured logging
8. Include metrics reporting with uppercase bank name
9. Use worker.Job pattern from reference exactly
10. Test coverage for all scenarios

## SUCCESS CRITERIA:
- All 7 integration points completed
- Code follows existing patterns exactly  
- No syntax or import errors
- Proper rate limiting configured
- Queue names are environment-specific
- Metrics and logging integrated
- Comprehensive test coverage
- Ready for production deployment

Execute this X-Balance integration following the reference patterns exactly, step by step.

{self._get_dynamic_git_authentication_instructions()}"""

    def _get_fts_service_prompt(self, bank_name: str, bank_upper: str, version: str) -> str:
        """Generate enhanced prompt for FTS service integration with reference patterns."""
        
        # Load FTS reference files for detailed context
        fts_references = self._load_fts_references()
        
        return f"""
You are a Go developer working on FTS (Fund Transfer Service) integration for {bank_upper} bank.

🛑 **IMMEDIATE TASK - DO THIS FIRST** 🛑

**YOUR FIRST ACTION MUST BE:**
1. Clone the repository: `gh repo clone razorpay/fts`
2. Navigate to FTS directory  
3. **IMMEDIATELY** edit these 2 critical files:
   - `internal/transfer/attempt_processor.go` (add {bank_upper} routing)
   - `internal/transfer/transfer_mode_processor.go` (add {bank_upper} modes)

🚨 **INTEGRATION WILL FAIL COMPLETELY WITHOUT THESE 2 CORE FILES** 🚨

**THESE FILES CONTAIN THE ROUTING LOGIC THAT DISPATCHES REQUESTS TO YOUR BANK.**
**WITHOUT MODIFYING THEM, NO REQUESTS WILL REACH {bank_upper} - THE INTEGRATION IS BROKEN.**

⛔ **YOU CANNOT CREATE BANK IMPLEMENTATION FILES UNTIL CORE ROUTING IS FIXED** ⛔

### 🔥 **MANDATORY SEQUENCE - NO SKIPPING:**

**STEP 1**: Edit `internal/transfer/attempt_processor.go`
- Find `getTaskNameForDispatchTransfer()` function
- Add `case channel.{bank_upper}:` section (copy IDFC pattern)
- Find `dispatchForStatusCheck()` function  
- Add `if processor.attempt.Channel == channel.{bank_upper}` section
- **VERIFY**: Run `grep "{bank_upper}" internal/transfer/attempt_processor.go`

**STEP 2**: Edit `internal/transfer/transfer_mode_processor.go`
- Add `{bank_upper} []string` to AllowedModes struct
- Add `case "{bank_upper}":` in getModeAndChannelByShortCode()
- Add `case "{bank_upper}":` in setMode()
- **VERIFY**: Run `grep "{bank_upper}" internal/transfer/transfer_mode_processor.go`

⚠️ **CHECKPOINT: If either grep shows NO results, STOP and fix before continuing.**

BANK CONFIGURATION:
- Bank Name: {bank_upper}
- Bank Short Code: {bank_name[:4].upper()}B  
- Version: {version}
- Supported Payment Modes: UPI, IMPS, NEFT, RTGS, IFT

KEY INTEGRATION POINTS FROM REFERENCE PATTERNS:

## 1. ENV.DEFAULT.TOML CONFIGURATION
{fts_references.get('env_config', 'Reference pattern not available')}

## 2. CHANNEL.GO MODIFICATIONS  
{fts_references.get('channel', 'Reference pattern not available')}

## 3. CONFIG/CHANNEL.GO MODIFICATIONS
{fts_references.get('config_channel', 'Reference pattern not available')}

## 4. ATTEMPT PROCESSOR MODIFICATIONS (USE THESE EXACT PATTERNS)
{fts_references.get('attempt_processor', 'Reference pattern not available')}

## 5. TRANSFER MODE PROCESSOR MODIFICATIONS (USE THESE EXACT PATTERNS)  
{fts_references.get('transfer_mode_processor', 'Reference pattern not available')}

## CUSTOM FTS INTEGRATION GUIDELINES
{fts_references.get('custom_prompt', 'Custom prompt not available')}

IMPLEMENTATION REQUIREMENTS:

### Files to Create/Modify

**CRITICAL: These existing files MUST be modified first (integration will fail without them):**

1. **internal/transfer/attempt_processor.go** - MANDATORY: Add {bank_upper} case to getTaskNameForDispatchTransfer() and dispatchForStatusCheck() functions
2. **internal/transfer/transfer_mode_processor.go** - MANDATORY: Add {bank_upper} to AllowedModes struct, getModeAndChannelByShortCode(), and setMode() functions
3. **internal/channel/channel.go** - MANDATORY: Add {bank_upper} constant, channels array, allowed modes mapping, GetApiConfig case
4. **internal/config/channel.go** - MANDATORY: Add {bank_upper} field to Channels struct with TOML binding

**Additional required files:**

5. **config/env.default.toml** - Add {bank_upper} worker mappings and task configurations  
6. **{bank_name.lower()}/{version}/constants.go** - Bank-specific constants
7. **{bank_name.lower()}/{version}/error_code.go** - Error definitions
8. **{bank_name.lower()}/{version}/gateway_model.go** - Data structures
9. **{bank_name.lower()}/{version}/base.go** - Base functionality
10. **{bank_name.lower()}/{version}/gateway_error_mapper.go** - Error mapping
11. **{bank_name.lower()}/{version}/action_store.go** - Action routing

**CRITICAL REQUIREMENT**: You MUST modify the existing core files (items 1-4) or the integration will not function. These are not optional - they contain the routing logic that dispatches requests to your bank.

### Critical Implementation Notes:
- Replace "IDFC" with "{bank_upper}" and "idfc" with "{bank_name.lower()}" throughout
- Replace "IDFB" with "{bank_name[:4].upper()}B" for short code mapping
- Support all payment modes: UPI, IMPS, NEFT, RTGS, IFT
- Include high volume UPI handling
- Support payroll account routing
- Add direct account vs regular account segregation
- Follow exact IDFC patterns for consistency

Execute step by step, following the reference patterns exactly.

{self._get_dynamic_git_authentication_instructions()}"""

    def _get_payouts_service_prompt(self, bank_name: str, bank_upper: str, version: str) -> str:
        """Generate enhanced prompt for Payouts service integration with reference patterns."""
        
        # Load Payouts reference files for detailed context
        payouts_references = self._load_payouts_references()
        
        return f"""
You are a Go developer working on Payouts service integration for {bank_upper} bank.

🛑 **IMMEDIATE TASK - DO THIS FIRST** 🛑

**YOUR FIRST ACTION MUST BE:**
1. Clone the repository: `gh repo clone razorpay/payouts`
2. Navigate to Payouts directory  
3. **IMMEDIATELY** edit these 4 critical configuration files:
   - `internal/app/common/appConstants/constants.go` (add {bank_upper} bank constant)
   - `internal/app/common/appConstants/accounts.go` (add virtual account prefixes)
   - `internal/app/payouts/mode.go` (add {bank_upper} to supported channels)
   - `internal/app/fundAccountCache/model_test.go` (add test patterns)

🚨 **INTEGRATION WILL FAIL COMPLETELY WITHOUT THESE 4 CORE CONFIG FILES** 🚨

**THESE FILES CONTAIN THE CHANNEL MAPPING AND ACCOUNT CONFIGURATION.**
**WITHOUT MODIFYING THEM, NO PAYOUTS WILL ROUTE TO {bank_upper} - THE INTEGRATION IS BROKEN.**

⛔ **YOU CANNOT CREATE BANK IMPLEMENTATION FILES UNTIL CORE CONFIG IS FIXED** ⛔

### 🔥 **MANDATORY SEQUENCE - NO SKIPPING:**

**STEP 1**: Edit `internal/app/common/appConstants/constants.go`
- Add `{bank_upper} = "{bank_upper}"` constant after existing bank constants
- **VERIFY**: Run `grep "{bank_upper}" internal/app/common/appConstants/constants.go`

**STEP 2**: Edit `internal/app/common/appConstants/accounts.go`
- Add {bank_upper} virtual account prefixes to `PrefixToIfscMappingForVirtualAccounts` map
- **VERIFY**: Run `grep "{bank_upper}" internal/app/common/appConstants/accounts.go`

**STEP 3**: Edit `internal/app/payouts/mode.go`
- Add {bank_upper} to `allSupportedChannels` map for India country
- **VERIFY**: Run `grep "{bank_upper}" internal/app/payouts/mode.go`

**STEP 4**: Edit `internal/app/fundAccountCache/model_test.go`
- Add {bank_upper} test patterns following existing bank examples
- **VERIFY**: Run `grep "{bank_upper}" internal/app/fundAccountCache/model_test.go`

⚠️ **CHECKPOINT: If any grep shows NO results, STOP and fix before continuing.**

## Repository Setup - RESILIENT NAVIGATION

{self._get_git_workflow_instructions(
    repository_name="payouts",
    bank_name=bank_name,
    service_name="Payouts",
    commit_details=f"""- Add {bank_upper} bank constants and configuration in appConstants/
- Update channel mappings and account configurations  
- Add virtual account prefixes and supported channels
- Create comprehensive test patterns for fund account cache
- Support for all payment modes and account types""",
    pr_body=f"""## Summary
This PR integrates {bank_upper} bank into the Payouts service, adding comprehensive support for payout operations.

## Changes Made
- **Updated**: appConstants/constants.go with {bank_upper} bank constant
- **Updated**: appConstants/accounts.go with virtual account prefixes
- **Updated**: payouts/mode.go with {bank_upper} supported channels
- **Updated**: fundAccountCache/model_test.go with test patterns
- **Support**: All payout modes and account configurations

## Verification
- ✅ {bank_upper} bank constant added to core constants
- ✅ Virtual account prefixes configured correctly
- ✅ Channel mappings updated for all payment modes
- ✅ Test patterns added and validated
- ✅ Configuration follows existing bank patterns

🤖 Generated with [Claude Code](https://claude.com/claude-code)"""
)}

## DIRECTORY NAVIGATION RULES:
1. **ALWAYS** use `pwd` to verify current directory
2. **PREFER** absolute paths: `"$SHELL_PWD/internal/app/payouts/mode.go"`
3. **USE** environment variables: `export SHELL_PWD="/path/to/payouts"`
4. **FALLBACK** patterns: `cd "$DIR" || cd "/tmp/payouts" || find . -name "payouts" -type d`
5. **UNIQUE** branch names with timestamp: `integrate-{bank_name.lower()}-$(date +%Y%m%d-%H%M%S)`
6. **VERIFY** with `ls -la` after every `cd` command

## COMMAND PATTERNS:
- File operations: `vim "$SHELL_PWD/internal/app/payouts/mode.go"`
- Search operations: `find "$SHELL_PWD" -name "*.go" -type f`
- Verification: `grep -r "{bank_upper}" "$SHELL_PWD/internal/"`

## IF DIRECTORY ISSUES PERSIST:
```bash
# Find payouts directory
find /tmp -name "payouts" -type d 2>/dev/null
# Use full paths
PAYOUTS_FULL_PATH=$(find /tmp -name "payouts" -type d 2>/dev/null | head -1)
cd "$PAYOUTS_FULL_PATH"
```

## EFFICIENCY GUIDELINES:
- **Time Limit**: Max 2 minutes for directory navigation
- **Quick Verification**: `pwd && ls -la | head -5`  
- **Pattern Recognition**: Look for `internal/`, `go.mod`, `Dockerfile`
- **Progressive Fallback**: Try method 1 → 2 → 3 until success
- **Early Detection**: If stuck >30 seconds, try next method

BANK CONFIGURATION:
- Bank Name: {bank_upper}
- Bank Short Code: {bank_name[:4].upper()}B  
- Version: {version}
- Supported Payout Modes: UPI, IMPS, NEFT, RTGS, IFT
- Service Type: Disbursement/Payouts

KEY INTEGRATION POINTS FROM REFERENCE PATTERNS:

## 1. PAYOUTS SERVICE OVERVIEW
{payouts_references.get('service', 'Reference pattern not available')}

## 2. ACCOUNTS.GO MODIFICATIONS  
{payouts_references.get('accounts', 'Reference pattern not available')}

## 3. CONSTANTS.GO MODIFICATIONS
{payouts_references.get('constants', 'Reference pattern not available')}

## 4. MODE.GO MODIFICATIONS (USE THESE EXACT PATTERNS)
{payouts_references.get('mode', 'Reference pattern not available')}

## 5. MODEL TEST PATTERNS
{payouts_references.get('model_test', 'Reference pattern not available')}

## 6. MODE TEST PATTERNS
{payouts_references.get('mode_test', 'Reference pattern not available')}

## 7. TEMPORARY MODIFICATIONS GUIDE
{payouts_references.get('temp_modifications', 'Reference pattern not available')}

IMPLEMENTATION REQUIREMENTS:

### Files to Create/Modify

**CRITICAL: These existing configuration files MUST be modified first (integration will fail without them):**

1. **internal/app/common/appConstants/constants.go** - MANDATORY: Add {bank_upper} bank constant
2. **internal/app/common/appConstants/accounts.go** - MANDATORY: Add virtual account prefixes and IFSC mappings
3. **internal/app/payouts/mode.go** - MANDATORY: Add {bank_upper} to allSupportedChannels for India
4. **internal/app/fundAccountCache/model_test.go** - MANDATORY: Add {bank_upper} test patterns

**Additional required files:**

5. **{bank_name.lower()}/{version}/constants.go** - Bank-specific constants and codes
6. **{bank_name.lower()}/{version}/models.go** - Payout request/response structures  
7. **{bank_name.lower()}/{version}/gateway.go** - Bank gateway implementation
8. **{bank_name.lower()}/{version}/webhook.go** - Webhook handling and status updates
9. **{bank_name.lower()}/{version}/mapper.go** - Status and error code mappings
10. **{bank_name.lower()}/{version}/validator.go** - Input validation and business rules
11. **{bank_name.lower()}/{version}/config.go** - Bank configuration and settings

### Critical Implementation Notes:
- Replace "RBL" or "ICICI" with "{bank_upper}" throughout reference patterns
- Replace "rbl" or "icici" with "{bank_name.lower()}" for package/file names  
- Support all payout modes: UPI, IMPS, NEFT, RTGS, IFT
- Include batch processing capabilities
- Add proper webhook signature verification
- Implement comprehensive status reconciliation
- Follow exact existing bank patterns for consistency
- Include proper fund account validation
- Add comprehensive audit trails

**CRITICAL REQUIREMENT**: You MUST modify the existing core configuration files (items 1-4) or the integration will not function. These are not optional - they contain the channel mappings and account configurations that route payouts to your bank.

### ⚡ COPY-PASTE INSTRUCTION FOR CORE FILES:
- **Find existing bank patterns** (RBL, ICICI, YESBANK) in each core file
- **Copy the exact structure** and replace bank names with {bank_upper}/{bank_name.lower()}
- **Maintain same positioning** - add {bank_upper} after existing banks
- **Keep same formatting** - tabs, spacing, struct alignment

⚠️ **FINAL VERIFICATION (MANDATORY BEFORE COMMIT):**
```bash
# Verify all 4 core files contain {bank_upper}:
grep "{bank_upper}" internal/app/common/appConstants/constants.go
grep "{bank_upper}" internal/app/common/appConstants/accounts.go  
grep "{bank_upper}" internal/app/payouts/mode.go
grep "{bank_upper}" internal/app/fundAccountCache/model_test.go

# If ANY command shows NO results, the integration is BROKEN
```

**🚨 CONSEQUENCES OF SKIPPING CORE FILES:**
- ❌ Payouts will fail routing to {bank_upper}
- ❌ Virtual accounts won't be recognized  
- ❌ Channel validation will reject {bank_upper} requests
- ❌ Tests will fail due to missing configurations
- ❌ **ENTIRE INTEGRATION WILL NOT WORK**

**CRITICAL**: Execute step by step in the EXACT order specified. DO NOT skip any MANDATORY steps.

{self._get_dynamic_git_authentication_instructions()}"""

    def _get_integrations_go_service_prompt(self, bank_name: str, bank_upper: str, version: str) -> str:
        """Generate detailed prompt for Integrations-Go service integration.""" 
        return f"""
# Bank Integration Task: {bank_upper} Bank Integrations-Go Service

You need to integrate {bank_upper} bank into the integrations-go service for gateway functionality.

## Your Task:
Create {bank_upper} bank gateway integration in the integrations-go service following established patterns.

## Required Files to Create/Update:

### 1. Create gateway implementation
- Create `internal/gateway/struct/{bank_name}/` directory structure
- Implement gateway interface following existing bank patterns
- Create request/response models and transformers
- Add proper API client with authentication

### 2. Create balance fetch implementation  
- Create `internal/gateway/struct/balance_fetch/{bank_name}/balance_fetch.go`
- Follow exact patterns from existing bank implementations
- Include proper error handling and response mapping
- Add timeout and retry logic

### 3. Update gateway configuration
- Add {bank_upper} to gateway configuration
- Include API endpoints, authentication details, and limits
- Configure proper request/response transformations
- Add gateway-specific settings and features

### 4. Create comprehensive tests
- Create `balance_fetch_test.go` with full test coverage
- Add unit tests for all gateway operations
- Include integration tests with mock responses
- Test error scenarios and edge cases

### 5. Update gateway registry
- Register {bank_upper} in the gateway factory
- Add proper initialization and configuration loading
- Include gateway capability definitions
- Update routing and selection logic

## CRITICAL Requirements:
- Follow integrations-go architectural patterns exactly  
- Implement proper request/response transformation
- Add comprehensive error handling and logging
- Include proper authentication and security
- Maintain consistency with existing gateways
- Use proper Go conventions and patterns

## Success Criteria:
- {bank_upper} gateway is fully functional
- Balance fetch operations work correctly
- All tests pass with good coverage
- Proper error handling and logging
- Configuration is production-ready
- Integration follows service patterns

Execute this X-Balance integration following the reference patterns exactly, step by step.

{self._get_dynamic_git_authentication_instructions()}"""

    def _get_terminals_service_prompt(self, bank_name: str, bank_upper: str, version: str) -> str:
        """Generate enhanced prompt for Terminals service integration with reference patterns."""
        
        # Load Terminals reference files for detailed context
        terminals_references = self._load_terminals_references()
        
        return f"""
You are a Go developer working on Terminals service integration for {bank_upper} bank.

🛑 **IMMEDIATE TASK - DO THIS FIRST** 🛑

**YOUR FIRST ACTION MUST BE:**
1. Clone the repository: `gh repo clone razorpay/terminals`
2. Navigate to Terminals directory  
3. **IMMEDIATELY** modify these 4 critical files in exact order:
   - `internal/gateway/constants.go` (add {bank_upper} constants to 4 locations)
   - `internal/gateway_credentials/validator.go` (add validation rules, case, and function)
   - `internal/gateway_credentials/validator_test.go` (add 3 test cases)
   - `slit/fts_{bank_name.lower()}_onboarding_test.go` (create new complete test file)

🚨 **INTEGRATION WILL FAIL COMPLETELY WITHOUT THESE 4 CORE FILES** 🚨

**THESE FILES CONTAIN THE GATEWAY DEFINITIONS AND CREDENTIAL VALIDATION.**
**WITHOUT MODIFYING THEM, {bank_upper} GATEWAY WON'T BE RECOGNIZED - THE INTEGRATION IS BROKEN.**

⛔ **YOU CANNOT SKIP ANY MODIFICATION - ALL 4 FILES ARE MANDATORY** ⛔

### 🔥 **MANDATORY SEQUENCE - NO SKIPPING:**

**STEP 1**: Edit `internal/gateway/constants.go`
- Add `Fts{bank_upper} = "fts_{bank_name.lower()}"` constant declaration
- Add to `SupportedGatewayList`, `EditGatewayList`, and `GatewaysWithMozartV2Credentials` arrays
- **VERIFY**: Run `grep "Fts{bank_upper}\\|fts_{bank_name.lower()}" internal/gateway/constants.go`

**STEP 2**: Edit `internal/gateway_credentials/validator.go`
- Add "fts_{bank_name.lower()}" entry to `gatewayCredentialRulesByGateway` map
- Add `case gateway.Fts{bank_upper}:` to `ValidateGatewayCredential` switch statement
- Create `ValidateFts{bank_upper}GatewayCredential` function
- **VERIFY**: Run `grep -i "{bank_upper}\\|{bank_name.lower()}" internal/gateway_credentials/validator.go`

**STEP 3**: Edit `internal/gateway_credentials/validator_test.go`
- Add 3 test cases for "fts_{bank_name.lower()}" in `TestValidateOptimizerGatewayCredential`
- **VERIFY**: Run `grep -c '"fts_{bank_name.lower()}"' internal/gateway_credentials/validator_test.go` (should show 3)

**STEP 4**: Create `slit/fts_{bank_name.lower()}_onboarding_test.go`
- Create complete new test file with success/failure scenarios
- **VERIFY**: Run `ls -la slit/fts_{bank_name.lower()}_onboarding_test.go`

⚠️ **CHECKPOINT: If any verification shows NO results, STOP and fix before continuing.**

## Repository Setup - RESILIENT NAVIGATION

{self._get_git_workflow_instructions(
    repository_name="terminals",
    bank_name=bank_name,
    service_name="Terminals",
    commit_details=f"""- Add {bank_upper} gateway constants to internal/gateway/constants.go (4 locations)
- Add gateway credential validation rules and functions  
- Create comprehensive test cases for validator functionality
- Add {bank_upper} onboarding test file following FTS patterns
- Support for terminal gateway operations and validation""",
    pr_body=f"""## Summary
This PR integrates {bank_upper} bank into the Terminals service, adding gateway support and credential validation.

## Changes Made
- **Updated**: internal/gateway/constants.go with {bank_upper} gateway constants (4 locations)
- **Updated**: internal/gateway_credentials/validator.go with validation rules and functions
- **Updated**: internal/gateway_credentials/validator_test.go with comprehensive test cases
- **Created**: slit/fts_{bank_name.lower()}_onboarding_test.go with complete test suite
- **Support**: Full terminal gateway operations and credential validation

## Verification
- ✅ {bank_upper} constants added to all required locations  
- ✅ Gateway credential validation rules implemented
- ✅ Validation functions and test cases added
- ✅ Onboarding test file created with full coverage
- ✅ All changes follow existing terminal patterns

🤖 Generated with [Claude Code](https://claude.com/claude-code)"""
)}

## DIRECTORY NAVIGATION RULES:
1. **ALWAYS** use `pwd` to verify current directory
2. **PREFER** absolute paths: `"$SHELL_PWD/internal/gateway/constants.go"`
3. **USE** environment variables: `export SHELL_PWD="/path/to/terminals"`
4. **FALLBACK** patterns: `cd "$DIR" || cd "/tmp/terminals" || find . -name "terminals" -type d`
5. **UNIQUE** branch names with timestamp: `integrate-{bank_name.lower()}-$(date +%Y%m%d-%H%M%S)`
6. **VERIFY** with `ls -la` after every `cd` command

BANK CONFIGURATION:
- Bank Name: {bank_upper}
- Bank Short Code: {bank_name[:4].upper()}B  
- Version: {version}
- Service Type: Payment Gateway/Terminals
- Gateway Type: FTS (Fund Transfer Service) integration

KEY INTEGRATION POINTS FROM REFERENCE PATTERNS:

## 1. CONSTANTS.GO MODIFICATIONS (USE THESE EXACT PATTERNS)
{terminals_references.get('constants', 'Reference pattern not available')}

## 2. VALIDATOR.GO MODIFICATIONS (USE THESE EXACT PATTERNS)  
{terminals_references.get('validator', 'Reference pattern not available')}

## 3. VALIDATOR TEST MODIFICATIONS (USE THESE EXACT PATTERNS)
{terminals_references.get('validator_test', 'Reference pattern not available')}

## 4. ONBOARDING TEST FILE CREATION (USE THIS COMPLETE TEMPLATE)
{terminals_references.get('onboarding_test', 'Reference pattern not available')}

IMPLEMENTATION REQUIREMENTS:

### Files to Modify/Create (MANDATORY ORDER)

**CRITICAL: These existing files MUST be modified first:**

1. **internal/gateway/constants.go** - MANDATORY: Add gateway constants to 4 locations
2. **internal/gateway_credentials/validator.go** - MANDATORY: Add validation rules, switch case, and function
3. **internal/gateway_credentials/validator_test.go** - MANDATORY: Add 3 comprehensive test cases
4. **slit/fts_{bank_name.lower()}_onboarding_test.go** - MANDATORY: Create complete new integration test file

### Critical Implementation Notes:
- Replace "IDFC" or "idfc" with "{bank_upper}" and "{bank_name.lower()}" throughout reference patterns
- Follow exact naming conventions: Fts{bank_upper} for constants, "fts_{bank_name.lower()}" for strings
- Maintain proper Go syntax, indentation, and formatting
- Include all required imports and dependencies
- Follow exact positioning specified in reference patterns

**CRITICAL REQUIREMENT**: You MUST modify/create all 4 files or the terminals integration will not function. These are not optional - they contain the gateway definitions, validation rules, and test coverage necessary for the terminals service to recognize and process {bank_upper} transactions.

### ⚡ COPY-PASTE INSTRUCTION FOR ALL FILES:
- **Find existing FTS bank patterns** (IDFC references) in each file
- **Copy the exact structure** and replace bank names with {bank_upper}/{bank_name.lower()}
- **Maintain same positioning** as specified in reference patterns
- **Keep same formatting** - indentation, spacing, brackets

⚠️ **FINAL VERIFICATION (MANDATORY BEFORE COMMIT):**
```bash
# Verify all 4 modifications completed:
grep -E "Fts{bank_upper}|fts_{bank_name.lower()}" internal/gateway/constants.go
grep -E "{bank_upper}|{bank_name.lower()}" internal/gateway_credentials/validator.go
grep -c '"fts_{bank_name.lower()}"' internal/gateway_credentials/validator_test.go
ls -la slit/fts_{bank_name.lower()}_onboarding_test.go

# If ANY command shows NO results, the integration is BROKEN
```

**🚨 CONSEQUENCES OF SKIPPING ANY FILE:**
- ❌ Gateway won't be recognized by terminals service
- ❌ Credential validation will fail for {bank_upper}
- ❌ No test coverage for integration verification  
- ❌ Onboarding will fail without proper test infrastructure
- ❌ **ENTIRE TERMINALS INTEGRATION WILL NOT WORK**

**CRITICAL**: Execute step by step in the EXACT order specified. DO NOT skip any MANDATORY steps.

{self._get_dynamic_git_authentication_instructions()}"""

    def _generate_random_suffix(self) -> str:
        """Generate a random 6-character suffix for branch names."""
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    
    def _load_xbalance_references(self) -> Dict[str, str]:
        """Load X-Balance reference files for detailed prompts."""
        references = {}
        
        # Get the prompt_providers directory
        from pathlib import Path
        base_dir = Path(__file__).parent / "prompt_providers"
        
        reference_files = {
            'job': 'xbalance_job_reference.txt',
            'channel': 'xbalance_channel_reference.txt', 
            'ratelimiter': 'xbalance_ratelimiter_reference.txt',
            'transformer': 'xbalance_transformer_reference.txt',
            'factory': 'xbalance_factory_reference.txt',
            'worker': 'xbalance_worker_reference.txt',
            'service_overview': 'xbalance_service_overview.txt'
        }
        
        for key, filename in reference_files.items():
            try:
                file_path = base_dir / filename
                if file_path.exists():
                    with open(file_path, 'r', encoding='utf-8') as f:
                        references[key] = f"This is the reference for x-balances {key} implementation patterns:\n\n" + f.read()
                else:
                    self.logger.warning(f"Reference file not found: {filename}")
                    references[key] = f"X-Balance {key} reference - please provide the {key} implementation patterns"
            except Exception as e:
                self.logger.error(f"Error loading reference file {filename}: {e}")
                references[key] = f"X-Balance {key} reference - error loading file"
        
        return references

    def _load_fts_references(self) -> Dict[str, str]:
        """Load FTS reference files from the server1.py extracted patterns."""
        references = {}
        
        # Get the prompt_providers directory
        from pathlib import Path
        base_dir = Path(__file__).parent / "prompt_providers"
        
        reference_files = {
            'env_config': 'fts_env_config.txt',
            'channel': 'fts_channel.txt',
            'attempt_processor': 'fts_attempt_processor.txt', 
            'transfer_mode_processor': 'fts_transfer_mode_processor.txt',
            'config_channel': 'fts_config_channel_reference.txt',
            'custom_prompt': 'fts_prompt.txt'
        }
        
        for key, filename in reference_files.items():
            try:
                file_path = base_dir / filename
                if file_path.exists():
                    with open(file_path, 'r', encoding='utf-8') as f:
                        references[key] = f"This is the reference for FTS {key} implementation patterns:\n\n" + f.read()
                else:
                    self.logger.warning(f"FTS reference file not found: {filename}")
                    references[key] = f"FTS {key} reference - please provide the {key} implementation patterns"
            except Exception as e:
                self.logger.error(f"Error loading FTS reference file {filename}: {e}")
                references[key] = f"FTS {key} reference - error loading file"
                
        return references

    def _load_payouts_references(self) -> Dict[str, str]:
        """Load Payouts reference files for detailed integration patterns."""
        references = {}
        
        # Get the prompt_providers directory
        from pathlib import Path
        base_dir = Path(__file__).parent / "prompt_providers"
        
        reference_files = {
            'service': 'payouts_service_reference.txt',
            'accounts': 'payouts_accounts_reference.txt',
            'constants': 'payouts_constants_reference.txt',
            'mode': 'payouts_mode_reference.txt',
            'mode_test': 'payouts_mode_test_reference.txt',
            'model_test': 'payouts_model_test_reference.txt',
            'temp_modifications': 'temp_payouts_modifications.txt'
        }
        
        for key, filename in reference_files.items():
            try:
                file_path = base_dir / filename
                if file_path.exists():
                    with open(file_path, 'r', encoding='utf-8') as f:
                        references[key] = f"This is the reference for Payouts {key} implementation patterns:\n\n" + f.read()
                else:
                    self.logger.warning(f"Payouts reference file not found: {filename}")
                    references[key] = f"Payouts {key} reference - please provide the {key} implementation patterns"
            except Exception as e:
                self.logger.error(f"Error loading Payouts reference file {filename}: {e}")
                references[key] = f"Payouts {key} reference - error loading file"
                
        return references

    def _load_terminals_references(self) -> Dict[str, str]:
        """Load Terminals reference files for detailed integration patterns."""
        references = {}
        
        # Get the prompt_providers directory
        from pathlib import Path
        base_dir = Path(__file__).parent / "prompt_providers"
        
        reference_files = {
            'constants': 'terminals_constants_reference.txt',
            'validator': 'terminals_validator_reference.txt',
            'validator_test': 'terminals_validator_test_reference.txt',
            'onboarding_test': 'terminals_onboarding_test_reference.txt'
        }
        
        for key, filename in reference_files.items():
            try:
                file_path = base_dir / filename
                if file_path.exists():
                    with open(file_path, 'r', encoding='utf-8') as f:
                        references[key] = f"This is the reference for Terminals {key} implementation patterns:\n\n" + f.read()
                else:
                    self.logger.warning(f"Terminals reference file not found: {filename}")
                    references[key] = f"Terminals {key} reference - please provide the {key} implementation patterns"
            except Exception as e:
                self.logger.error(f"Error loading Terminals reference file {filename}: {e}")
                references[key] = f"Terminals {key} reference - error loading file"
                
        return references

    async def integrate_kube_manifests_service(self, state: BankIntegrationState) -> Dict[str, Any]:
        """Integrate Kube-manifests service with AI code generation."""
        task_id = state["task_id"]
        bank_name = state["bank_name"]
        version = state["version"]
        bank_upper = bank_name.upper()
        branch_name = state["working_branch"].get("kube-manifests", f"feature/kube-manifests-{bank_name.lower()}-integration")
        
        self.logger.info(f"Starting Kube-manifests integration for {bank_name}")
        
        try:
            agent_tool = AutonomousAgentTool()
            
            # Get enhanced kube-manifests prompt with reference patterns
            kube_manifests_prompt = self._get_kube_manifests_service_prompt(bank_name, bank_upper, version)
            
            integration_result = await agent_tool.run_autonomous_task(
                repository_url=BankRepositoryConfig.KUBE_MANIFESTS,
                branch_name=branch_name,
                task_description=f"Integrate {bank_upper} bank into Kube-manifests service",
                prompt=kube_manifests_prompt,
                max_iterations=state.get("max_iterations", 50)
            )
            
            if integration_result.get("success"):
                return {
                    "success": True,
                    "service": "kube-manifests",
                    "bank_name": bank_name,
                    "pr_url": integration_result.get("pr_url"),
                    "files_created": integration_result.get("files_modified", []),
                    "branch_name": branch_name,
                    "integration_type": "values_yaml_and_deployment_templates"
                }
            else:
                return {
                    "success": False,
                    "service": "kube-manifests",
                    "bank_name": bank_name,
                    "error": integration_result.get("error", "Unknown error"),
                    "branch_name": branch_name
                }
                
        except Exception as e:
            self.logger.error(f"Kube-manifests integration exception for {bank_name}: {e}")
            return {
                "success": False,
                "service": "kube-manifests",
                "bank_name": bank_name,
                "error": str(e),
                "branch_name": branch_name
            }

    def _get_kube_manifests_service_prompt(self, bank_name: str, bank_upper: str, version: str) -> str:
        """Generate comprehensive prompt for Kube-manifests service integration."""
        
        # Load reference files for detailed patterns
        references = self._load_kube_manifests_references()
        
        return f"""
YOU ARE A KUBERNETES CONFIGURATION EXPERT tasked with integrating {bank_upper} bank into the kube-manifests service.

🛑 **IMMEDIATE TASK - DO THIS FIRST** 🛑

**YOUR FIRST ACTION MUST BE:**
1. Clone the repository: `gh repo clone razorpay/kube-manifests`
2. Navigate to kube-manifests directory  
3. **IMMEDIATELY** update and create these files:
   - `kube-manifests/prod/fts/values.yaml` (add {bank_upper} worker replica configurations)
   - Create 18 deployment template files in `kube-manifests/templates/fts/templates/`

🚨 **INTEGRATION WILL FAIL COMPLETELY WITHOUT THESE CRITICAL FILES** 🚨

**THESE FILES CONTAIN THE KUBERNETES WORKER CONFIGURATIONS AND DEPLOYMENT TEMPLATES.**
**WITHOUT UPDATING THEM, {bank_upper} BANK WORKERS WILL NOT BE DEPLOYED - THE INTEGRATION IS BROKEN.**

**TARGET BANK:** {bank_upper} ({bank_name.lower()})
**VERSION:** {version}

## Repository Setup - RESILIENT NAVIGATION

{self._get_git_workflow_instructions(
    repository_name="kube-manifests",
    bank_name=bank_name,
    service_name="Kube-manifests",
    commit_details=f"""- Add {bank_upper} worker replica configurations to prod/fts/values.yaml (54 configs)
- Create 18 Kubernetes deployment templates for {bank_upper} bank operations:
  * Core operations: initiate_transfer, check_transfer_status  
  * UPI, IMPS, NEFT, RTGS operations (standard and direct)
  * Each template includes main, canary, and baseline deployments
- Support for all payment channels and deployment environments""",
    pr_body=f"""## Summary
This PR integrates {bank_upper} bank into the kube-manifests service, adding comprehensive support for all payment channels and deployment environments.

## Changes Made
- **Updated**: prod/fts/values.yaml with 54 {bank_upper} worker replica configurations
- **Created**: 18 Kubernetes deployment template files in templates/fts/templates/
- **Support**: All payment channels (Core, UPI, IMPS, NEFT, RTGS, Direct variants)

## Verification
- ✅ All 54 worker replica configurations added to values.yaml
- ✅ All 18 deployment template files created successfully
- ✅ Template files follow correct naming conventions  
- ✅ Template variables and worker arguments are correct
- ✅ YAML syntax validated in all files
- ✅ Changes committed and pushed to feature branch

🤖 Generated with [Claude Code](https://claude.com/claude-code)"""
)}

**CRITICAL BLOCKING INSTRUCTIONS - READ BEFORE EXECUTION:**

🚫 **EXECUTION BLOCKERS - STOP IMMEDIATELY IF ANY ARE VIOLATED:**

1. **YAML SYNTAX VALIDATION**: Every YAML file (values.yaml + 18 templates) MUST be syntactically valid
2. **VALUES.YAML INSERTION POINT**: Changes MUST be added above the `#### Canary/Baseline` comment
3. **NAMING CONVENTION ENFORCEMENT**: All worker names and file names MUST follow specified patterns
4. **REPLICA COUNT CONSISTENCY**: All replica counts MUST be set to 1 in values.yaml
5. **TEMPLATE FILE COMPLETENESS**: ALL 18 deployment template files MUST be created
6. **WORKER ARGS ACCURACY**: Template worker arguments MUST match operation types exactly
7. **INDENTATION PRECISION**: YAML indentation MUST be exact (2 spaces per level)
8. **TEMPLATE STRUCTURE**: Each template MUST include main, canary, and baseline deployments

**INTEGRATION TASK:**

Your task is to integrate {bank_upper} bank into the kube-manifests service by:
1. Updating the values.yaml file with worker replica configurations  
2. Creating 18 Kubernetes deployment template files

**FILES TO MODIFY/CREATE:**
- **Update**: `kube-manifests/prod/fts/values.yaml`
- **Create**: 18 deployment template files in `kube-manifests/templates/fts/templates/`

**VALUES.YAML INTEGRATION REFERENCE:**

{references.get('values', 'No values.yaml reference available')}

**DEPLOYMENT TEMPLATES INTEGRATION REFERENCE:**

{references.get('templates', 'No templates reference available')}

**STEP-BY-STEP EXECUTION PLAN:**

**PHASE 1: VALUES.YAML UPDATE**

**STEP 1: Locate and Analyze values.yaml**
- Navigate to `kube-manifests/prod/fts/values.yaml`
- Locate the `#### Canary/Baseline` comment marker
- Verify the insertion point is correct

**STEP 2: Add Worker Replica Configurations**
Add all 32 worker replica configurations ABOVE the `#### Canary/Baseline` comment as specified in the VALUES.YAML INTEGRATION REFERENCE section above. Replace `newbank` with `{bank_name.lower()}` in all configuration names.

**STEP 3: Validate values.yaml Changes**
1. Verify YAML syntax is correct
2. Confirm all 32 worker configurations are added
3. Ensure proper indentation (2 spaces)
4. Validate insertion point (above `#### Canary/Baseline`)
5. Check naming convention consistency

**PHASE 2: DEPLOYMENT TEMPLATE FILES CREATION**

**STEP 4: Create Template Files Directory Structure**
- Navigate to `kube-manifests/templates/fts/templates/`
- Prepare to create 18 new deployment template files

**STEP 5: Create Core Operations Templates (2 files)**
Create these files with appropriate templates:
1. `fts-live-worker-{bank_name.lower()}-initiate-transfer-deployment.yaml`
2. `fts-live-worker-{bank_name.lower()}-check-transfer-status-deployment.yaml`

**STEP 6: Create UPI Operations Templates (2 files)**
3. `fts-live-worker-{bank_name.lower()}-upi-initiate-transfer-deployment.yaml`
4. `fts-live-worker-{bank_name.lower()}-upi-check-transfer-status-deployment.yaml`

**STEP 7: Create IMPS Operations Templates (2 files)**
5. `fts-live-worker-{bank_name.lower()}-imps-initiate-transfer-deployment.yaml`
6. `fts-live-worker-{bank_name.lower()}-imps-check-transfer-status-deployment.yaml`

**STEP 8: Create NEFT Operations Templates (2 files)**
7. `fts-live-worker-{bank_name.lower()}-neft-initiate-transfer-deployment.yaml`
8. `fts-live-worker-{bank_name.lower()}-neft-check-transfer-status-deployment.yaml`

**STEP 9: Create RTGS Operations Templates (2 files)**
9. `fts-live-worker-{bank_name.lower()}-rtgs-initiate-transfer-deployment.yaml`
10. `fts-live-worker-{bank_name.lower()}-rtgs-check-transfer-status-deployment.yaml`

**STEP 10: Create Direct UPI Operations Templates (2 files)**
11. `fts-live-worker-{bank_name.lower()}-direct-upi-initiate-transfer-deployment.yaml`
12. `fts-live-worker-{bank_name.lower()}-direct-upi-check-transfer-status-deployment.yaml`

**STEP 11: Create Direct IMPS Operations Templates (2 files)**
13. `fts-live-worker-{bank_name.lower()}-direct-imps-initiate-transfer-deployment.yaml`
14. `fts-live-worker-{bank_name.lower()}-direct-imps-check-transfer-status-deployment.yaml`

**STEP 12: Create Direct NEFT Operations Templates (2 files)**
15. `fts-live-worker-{bank_name.lower()}-direct-neft-initiate-transfer-deployment.yaml`
16. `fts-live-worker-{bank_name.lower()}-direct-neft-check-transfer-status-deployment.yaml`

**STEP 13: Create Direct RTGS Operations Templates (2 files)**
17. `fts-live-worker-{bank_name.lower()}-direct-rtgs-initiate-transfer-deployment.yaml`
18. `fts-live-worker-{bank_name.lower()}-direct-rtgs-check-transfer-status-deployment.yaml`

**STEP 14: Validate All Template Files**
1. Verify all 18 template files are created
2. Check YAML syntax in each file
3. Validate template variable names
4. Confirm worker arguments are correct
5. Ensure canary/baseline conditionals are included

**MANDATORY VERIFICATION CHECKLIST:**
**Values.yaml Updates:**
- [ ] Values.yaml file located and opened
- [ ] Insertion point identified (above `#### Canary/Baseline`)
- [ ] All 32 worker replicas added with correct names
- [ ] YAML syntax validated in values.yaml
- [ ] Indentation verified (2 spaces)
- [ ] All replica counts set to 1

**Template Files Creation:**
- [ ] All 18 deployment template files created
- [ ] Correct file naming convention followed
- [ ] Template variables properly set for each file
- [ ] Worker arguments correctly configured
- [ ] Canary/baseline conditionals included
- [ ] YAML syntax validated in all template files

**EXECUTION CONSTRAINTS:**
- **Values.yaml**: ONLY modify `kube-manifests/prod/fts/values.yaml`
- **Templates**: CREATE 18 new files in `kube-manifests/templates/fts/templates/`
- DO NOT modify existing template files
- DO NOT change existing configurations in values.yaml
- MAINTAIN exact YAML formatting in all files
- PRESERVE all existing comments and structure

**SUCCESS CRITERIA:**
✅ Values.yaml successfully updated with {bank_upper} worker configurations
✅ All 32 worker replica settings added to values.yaml
✅ All 18 deployment template files created successfully
✅ Template files follow correct naming conventions
✅ Template variables and worker arguments are correct
✅ YAML syntax valid in all files (values.yaml + 18 templates)
✅ Changes committed and pushed to feature branch
✅ Pull request created with comprehensive description

**CRITICAL**: Execute step by step in the EXACT order specified. DO NOT skip any MANDATORY steps.

{self._get_dynamic_git_authentication_instructions()}"""

    def _load_kube_manifests_references(self) -> Dict[str, str]:
        """Load Kube-manifests reference files for detailed integration patterns."""
        references = {}
        
        # Get the prompt_providers directory
        from pathlib import Path
        base_dir = Path(__file__).parent / "prompt_providers"
        
        reference_files = {
            'values': 'kube_manifests_values_reference.txt',
            'templates': 'kube_manifests_templates_reference.txt'
        }
        
        for key, filename in reference_files.items():
            try:
                file_path = base_dir / filename
                if file_path.exists():
                    with open(file_path, 'r', encoding='utf-8') as f:
                        references[key] = f"This is the reference for Kube-manifests {key} implementation patterns:\n\n" + f.read()
                else:
                    self.logger.warning(f"Kube-manifests reference file not found: {filename}")
                    references[key] = f"Kube-manifests {key} reference - please provide the {key} implementation patterns"
            except Exception as e:
                self.logger.error(f"Error loading Kube-manifests reference file {filename}: {e}")
                references[key] = f"Kube-manifests {key} reference - error loading file"
                
        return references


# Register the service using the global registry instance
from ..registry import service_registry
service_registry.register("bank-integration", BankIntegrationService)
