"""
Kubemanifest repository prompt provider for E2E onboarding.

Provides prompts for the kubemanifest repository processing step
with automatic branch detection and reuse capabilities.
"""

from typing import Optional, Dict, Any
from ..state import E2EOnboardingState


class KubemanifestPromptProvider:
    """Provides prompts for kubemanifest repository integration in E2E onboarding workflow."""

    def __init__(self):
        pass

    def get_base_prompt(self, service: str, repository_path: str, branch_name: str) -> str:
        """Generate the base prompt for kubemanifest repository integration."""
        return f"""
You are a principal site reliability engineer, expert in devops technologies like Kubernetes, yaml templating and Helm charts, tasked with setting up E2E onboarding configuration for service '{service}' in the kube-manifests repository.

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
7. Write brief yet up to the point commit message for the changes you made.
8. The PR will be automatically updated with your new commits
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
6. Write brief yet up to the point commit message for the changes you made.
7. Ensure the description of the pull request is concise and to the point and doesn't contain any unnecessary details.
8. Keep the description as a checklist of the changes you made.
9. Add a proper title: E2E onboarding configuration for {existing_pr_info.get('service', '')} service to the pull request.
10. After making changes, create a new PR for this branch
"""

    def get_new_branch_prompt(self, branch_name: str, existing_pr_info: Dict[str, Any]) -> str:
        """Generate prompt for new branch creation."""
        return f"""
NEW BRANCH CREATION:

No existing work found for this integration.

FOLLOW THESE STEPS:

1. Clone the repository with depth of 1, if not already done
2. Create a new branch: {branch_name}
3. Implement the required changes
4. Write brief yet up to the point commit message for the changes you made.
5. Ensure the description of the pull request is concise and to the point and doesn't contain any unnecessary details.
6. Keep the description as a checklist of the changes you made.
7. Add a proper title: E2E onboarding configuration for {existing_pr_info.get('service', '')} service to the pull request.
8. Create a new PR for your changes
"""

    def get_kubemanifest_specific_prompt(self, state: E2EOnboardingState, repository_path: str) -> str:
        """Generate kubemanifest-specific integration instructions."""
        return f"""
**KUBE-MANIFESTS INTEGRATION TASK**:

Add E2E testing configuration to the kube-manifests repository for the {state['service']} service.

**What you need to do**:
1. Using the input parameters provided in {state['input_parameters']}, extract the ephemeral database, database_env_keys and db_migration configs and use it to configure the ephemeral database as required in the next step.
2. Reference and follow the detailed instructions in {repository_path}/{state['input_parameters'].get('markdown_doc_path', '/e2e-onboarding.md')} within the kube-manifests repository located at the root of the {repository_path} repository path.
3. Verify whether you are able to successfully refer the instructions in the markdown file and configure the ephemeral database as required.

**Expected Outcome**: 
- You should be able to successfully refer the instructions in the markdown file and configure the ephemeral database as required.
- A valid kube-manifests configuration is present in the kube-manifests repository for the {state['service']} service with ephemeral database configuration.
- You should be able to verify the ephemeral database configuration by running the E2E tests.
"""

    def build_complete_prompt(self,
                              state: E2EOnboardingState,
                              repository_path: str,
                              branch_name: str,
                              existing_pr_info: Optional[Dict[str, Any]] = None) -> str:
        """Build the complete prompt by combining all prompt sections."""
         
        # Start with base prompt
        complete_prompt = self.get_base_prompt(state['service'], repository_path, branch_name)

        existing_pr_info['service'] = state['service']
        # Add existing PR/branch context if applicable
        if existing_pr_info and existing_pr_info.get("exists", False):
            complete_prompt += self.get_existing_pr_prompt(existing_pr_info)
        else:
            complete_prompt += self.get_new_branch_prompt(branch_name, existing_pr_info)

        # Add kubemanifest-specific instructions
        complete_prompt += self.get_kubemanifest_specific_prompt(state, repository_path)

        return complete_prompt 