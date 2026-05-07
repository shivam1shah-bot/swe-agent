"""
Service Repository prompt provider for E2E onboarding.

Provides prompts for the service_repo processing step
with automatic branch detection and reuse capabilities.
"""

from typing import Optional, Dict, Any
from ..state import E2EOnboardingState


class ServiceRepoPromptProvider:
    """Provides prompts for service repository integration in E2E onboarding workflow."""

    def __init__(self):
        pass

    def get_base_prompt(self, service: str, repository_path: str, branch_name: str) -> str:
        """Generate the base prompt for service repository integration."""
        return f"""
You are a principal developer with expertise in continuous integration and deployment, tasked with setting up E2E onboarding configuration for service '{service}' in the service repository.

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
9. Update the PR description highlighting to remove existing e2e configurations if present for the user.
10. Add a proper title: E2E onboarding configuration for {existing_pr_info.get('service', '')} service to the pull request.
11. After making changes, create a new PR for this branch
"""

    def get_new_branch_prompt(self, branch_name: str, existing_pr_info: Dict[str, Any]) -> str:
        """Generate prompt for new branch creation."""
        return f"""
NEW BRANCH CREATION:

No existing work found for this integration.

FOLLOW THESE STEPS:

1. Clone the repository with depth of 1, if not already done
2. Create a new branch: {branch_name}
3. Set up the initial E2E onboarding configuration
4. Implement the required changes
5. Write brief yet up to the point commit message for the changes you made.
6. Ensure the description of the pull request is concise and to the point and doesn't contain any unnecessary details.
7. Keep the description as a checklist of the changes you made.
8. Update the PR description highlighting to remove existing e2e configurations if present for the user.
9. Add a proper title: E2E onboarding configuration for {existing_pr_info.get('service', '')} service to the pull request.
10. Create a new PR for your changes
"""

    def get_service_repo_specific_prompt(self, state: E2EOnboardingState, template_path: str) -> str:
        """Generate service repository-specific integration instructions."""
        return f"""
**SERVICE REPOSITORY INTEGRATION TASK**:

Add E2E testing support configuration to the {state['service']} service repository.

**What you need to do**:
1. Reference Template:Locate the E2E workflow template at {template_path}.
2. Verify whether you are able to successfully refer the template file.
3. Update or Create e2e.yaml based on following steps:
    a. In the {state['service']} repository, go to the .gitHub workflows directory.
    b. If an e2e.yaml already exists, update it using the latest structure from the template.
    c. If it does not exist, create a new e2e.yaml file using the template.
4. IMPORTANT: Ensure the file generated should strongly match to template file.
5. YAML Validation:
    a. Ensure the e2e.yaml file is valid YAML syntax and passes any schema checks.  

**Expected Outcome**: 
1. You should be able to successfully refer the instructions in the template file.
2. A valid e2e.yaml file is present in the GitHub workflows directory of {state['service']}.
"""

    def build_complete_prompt(self,
                              state: E2EOnboardingState,
                              repository_path: str,
                              branch_name: str,
                              existing_pr_info: Optional[Dict[str, Any]] = None) -> str:
        """Build the complete prompt by combining all prompt sections."""
        
        template_path = '/templates/e2e.yaml'
        # Start with base prompt
        complete_prompt = self.get_base_prompt(state['service'], repository_path, branch_name)

        existing_pr_info['service'] = state['service']
        # Add existing PR/branch context if applicable
        if existing_pr_info and existing_pr_info.get("exists", False):
            complete_prompt += self.get_existing_pr_prompt(existing_pr_info)
        else:
            complete_prompt += self.get_new_branch_prompt(branch_name, existing_pr_info)

        # Add service repository-specific instructions
        complete_prompt += self.get_service_repo_specific_prompt(state, template_path)

        return complete_prompt