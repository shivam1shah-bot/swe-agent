"""
E2E Test Orchestrator repository prompt provider for E2E onboarding.

Provides prompts for the e2e_test_orchestrator repository processing step
with automatic branch detection and reuse capabilities.
"""

import json
from typing import Optional, Dict, Any
from ..state import E2EOnboardingState
from ..helper import generate_branch_name


class E2ETestOrchestratorPromptProvider:
    """Provides prompts for e2e_test_orchestrator repository integration in E2E onboarding workflow."""

    def __init__(self):
        pass

    def get_base_prompt(self, service: str, repository_path: str, branch_name: str) -> str:
        """Generate the base prompt for e2e_test_orchestrator repository integration."""
        return f"""
You are a principal developer tasked with setting up E2E onboarding configuration for service '{service}' in the e2e_test_orchestrator repository.

Repository: {repository_path}
Branch Name: {branch_name}
Service: {service}
"""

    def get_existing_pr_prompt(self, existing_pr_info: Dict[str, Any]) -> str:
        """Generate prompt for existing PR scenarios."""
        if existing_pr_info.get("pr_url"):
            return f"""
IMPORTANT - EXISTING PR DETECTED:

- Existing PR: {existing_pr_info.get('pr_url', 'N/A')}
- Existing Branch: {existing_pr_info.get('branch', 'N/A')}
- PR Number: {existing_pr_info.get('pr_number', 'N/A')}

DO NOT CREATE A NEW PR. Instead:

1. Clone the repository with depth of 1, if not already done
2. Checkout to the existing branch: {existing_pr_info.get('branch', 'N/A')}
3. Review the existing changes in this branch
4. Build upon the existing work - do not start from scratch
5. Update and improve the existing implementation
6. Commit additional changes to the same branch
7. The PR should be automatically updated with your new commits
"""
        else:
            return f"""
IMPORTANT - EXISTING BRANCH DETECTED:

- Existing Branch: {existing_pr_info.get('branch', 'N/A')}
- No PR exists yet for this branch

FOLLOW THESE STEPS:

1. Clone the repository with depth of 1, if not already done
2. Checkout to the existing branch: {existing_pr_info.get('branch', 'N/A')}
3. Review the existing changes in this branch
4. Build upon the existing work - do not start from scratch
5. Update and improve the existing implementation
6. After making changes, create a new PR for this branch
"""

    def get_new_branch_prompt(self, branch_name: str) -> str:
        """Generate prompt for new branch creation."""
        return f"""
NEW BRANCH CREATION:

No existing work found for this integration.

FOLLOW THESE STEPS:

1. Clone the repository with depth of 1, if not already done
2. Create a new branch: {branch_name}
3. Set up the initial E2E onboarding configuration
4. Implement the required changes
5. Create a new PR for your changes
"""

    def get_e2e_orchestrator_specific_prompt(
        self,
        state: E2EOnboardingState,
        repository_path: str,
        branch_name: str,
    ) -> str:
        """Generate e2e_test_orchestrator-specific integration instructions."""
        service = state["service"]
        params = state.get("input_parameters", {})
        kube_branch = generate_branch_name(service)

        return f"""
 **E2E TEST ORCHESTRATOR INTEGRATION TASK**:
 
 Add E2E test orchestration configuration for the {service} service.
 
 **What you need to do**:
-1. Stay on branch `{branch_name}` and reference and follow the detailed instructions in {repository_path}/{state['input_parameters'].get('markdown_doc_path', '/e2e-onboarding.md')} 
-2. Use the onboarding inputs from {state['input_parameters']}—including `chart_overrides`, `secrets`, `use_ephemeral_db`, and `e2e_test_orchestrator_params`—to update:
    - `e2e-action/service_configs/{service}.json`
    - `internal/app_configurations/{service}.json`
    - Any additional files listed in `{repository_path}/e2e-onboarding.md`
3. Ensure `additional_argo_params.kube_manifests_ref` points to `{kube_branch}` and keep storage/secret settings match with the inputs before committing changes.
 
 **Expected Outcome**:
 - You should be able to successfully refer the instructions in the markdown file and configure the E2E onboarding configuration as required.
 - Service and app configuration files reflect the onboarding inputs and are ready for automated test orchestration
 - All instructions in the doc are satisfied with concise commits and PR summary
 """

    def build_complete_prompt(self,
                              state: E2EOnboardingState,
                              repository_path: str,
                              branch_name: str,
                              existing_pr_info: Optional[Dict[str, Any]] = None) -> str:

        """Build the complete prompt by combining all prompt sections."""
        
        # Extract service and existing PR info from state
        service = state["service"]
        
        # Start with base prompt
        complete_prompt = self.get_base_prompt(service, repository_path, branch_name)

        # Add existing PR/branch context if applicable
        if existing_pr_info and existing_pr_info.get("exists", False):
            complete_prompt += self.get_existing_pr_prompt(existing_pr_info)
        else:
            complete_prompt += self.get_new_branch_prompt(branch_name)

        # Add e2e_test_orchestrator-specific instructions
        complete_prompt += self.get_e2e_orchestrator_specific_prompt(
            state=state,
            repository_path=repository_path,
            branch_name=branch_name,
        )

        return complete_prompt 