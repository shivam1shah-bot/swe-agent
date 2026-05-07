from typing import Dict, List, Any, Optional


class IntegrationsGoPromptProvider:
    """Provides prompts for integrations_go repository integration"""

    def __init__(self):
        pass

    def get_base_prompt(self, gateway_name: str, method: str, repository_path: str, standard_branch_name: str) -> str:
        """Generate the base prompt for integration"""
        return f"""
            You are software developer tasked with integrating the {gateway_name} payment gateway for {method} payments in the integrations-go repository with {method} functionality.
            Repository: {repository_path}
            Standard Branch Name: {standard_branch_name}
            IMPORTANT: Follow the integration documentation and reference implementation with special focus on {method} payment routing.
            """

    def get_existing_pr_prompt(self, existing_pr_info: Dict[str, Any]) -> str:
        """Generate prompt for existing PR scenarios"""
        if existing_pr_info.get("pr_url"):
            return f"""
            IMPORTANT - EXISTING PR DETECTED:

            - Existing PR: {existing_pr_info.get('pr_url', 'N/A')}
            - Existing Branch: {existing_pr_info.get('branch', 'N/A')}
            - PR Number: {existing_pr_info.get('pr_number', 'N/A')}
            DO NOT CREATE A NEW PR. Instead:

            1. Clone the repository if not already done
            2. Checkout to the existing branch: {existing_pr_info.get('branch', 'N/A')}
            3. Review the existing changes in this branch
            4. Build upon the existing work - do not start from scratch
            5. Update and improve the existing implementation
            6. Commit additional changes to the same branch
            7. The PR will be automatically updated with your new commits
            """
        else:
            return f"""
            IMPORTANT - EXISTING BRANCH DETECTED:

            - Existing Branch: {existing_pr_info.get('branch', 'N/A')}
            - No PR exists yet for this branch
            FOLLOW THESE STEPS:

            1. Clone the repository if not already done
            2. Checkout to the existing branch: {existing_pr_info.get('branch', 'N/A')}
            3. Review the existing changes in this branch
            4. Build upon the existing work - do not start from scratch
            5. Update and improve the existing implementation
            6. Commit additional changes to the same branch
            7. Create a NEW PR for this branch
            """

    def get_new_branch_prompt(self, standard_branch_name: str) -> str:
        """Generate prompt for new branch creation"""
        return f"""
            BRANCH CREATION:

            - Create a new branch with the name: {standard_branch_name}
            - This follows our standardized naming convention
            CREATE A NEW PR.
            1. Review the changes in this branch
            2. Commit changes in this branch
            3. The PR should be automatically updated with your new commits
            """

    def get_integrations_specific_prompt(self, gateway_name: str, formatted_apis_str: str,
                                         documentation_path: Optional[str] = None, reference_gateway: Optional[str] = None,
                                         use_switch: bool = False) -> str:
        """Generate integrations-specific instructions for payment gateway integration.
        
        Args:
            documentation_path: Path to the documentation file to include
            reference_gateway: Name of a reference gateway to use as a template
            gateway_name: gateway name
            formatted_apis_str : formatted_apis_str
            use_switch: Whether to enable switch functionality
        """
        
        # Handle None values with meaningful defaults or conditional inclusion
        reference_gateway_text = f"{reference_gateway}" if reference_gateway else "check other reference implementation"
        documentation_text = documentation_path if documentation_path else "integration documentation and best practices"
        
        
        return f"""
            INTEGRATIONS-GO SPECIFIC INSTRUCTIONS:
            PAYMENT METHOD - SPECIAL REQUIREMENTS:
            * Proceed with a gateway integration based on below :
                -> Take below values as input: 
                    <gateway>{gateway_name}</gateway>
                    <reference gateway>{reference_gateway_text}</reference gateway>
                    <documentation>{documentation_text}</documentation>
                    <switch>{'true' if use_switch else 'false'}</switch>
                -> go to integrations-go if not already in the folder     
                -> Read below files 
                    - .cursor/rules/001_master-rule.mdc
                    - .cursor/rules/reference_mds/gateway-description.md
                    - .cursor/rules/reference_mds/key-implementations.md
                    - .cursor/rules/reference_mds/implmentation-guidelines.md
                    - .cursor/rules/reference_mds/references.md
            
            * Integrate below api's:
            {formatted_apis_str}
            *  * Additional Requirements:
                - Quality Gates: Ensure 0 linting errors and successful compilation
                - No TODOs or linting errors in production code.
            * CRITICAL REQUIREMENTS:
                - NO hallucinated functions or imports
                - Code MUST compile successfully with go build
                - Follow exact patterns from reference implementation
                - Lint checks MUST pass (golint, gofmt, go vet)
                - Comprehensive error handling for all APIs
                - Don't generate unit test
            Strictly ensure all changes:
            - Include all APIs specified in apis_to_integrate
            - Pass all lint checks and compile successfully
            - Follow Go best practices and existing code patterns
            - No TODO's to be left            
    """

    def get_retry_context_prompt(self, current_iteration: int, previous_iterations: List[Dict[str, Any]]) -> str:
        """Generate retry context prompt"""
        retry_context = f"""
        RETRY ITERATION {current_iteration}:

        This is a retry attempt. Previous iterations have been made with the following results:

        """

        for iteration in previous_iterations:
            retry_context += f"""
        - Iteration {iteration['iteration']}: {'Success' if iteration['success'] else 'Failed'}
          Files modified: {', '.join(iteration.get('files_modified', []))}
          Message: {iteration.get('message', 'No message')}
        """

        retry_context += """

        IMPORTANT FOR RETRY:
        1. Build upon your previous work in the integrations-go repository
        2. Do not start from scratch - review existing changes first
        3. Focus specifically on addressing the feedback issues related to:
           - service integration problems
           - Payment routing logic compilation errors
           - configuration issues
           - Test failures
        4. Maintain existing functionality while fixing identified problems
        5. Ensure all APIs are properly implemented
        6. Verify routing logic is working correctly
        7. Test fallback scenarios when service is unavailable
        """
        return retry_context

    def build_complete_prompt(self, gateway_name: str, method: str, repository_path: str,
                              standard_branch_name: str, existing_pr_info: Dict[str, Any],
                              apis_to_integrate: List[str], is_retry: bool = False,
                              previous_iterations: Optional[List[Dict]] = None, documentation_path: Optional[str] = None,
                              reference_gateway: Optional[str] = None, use_switch: bool = False) -> str:
        """Build the complete prompt by combining all prompt sections"""

        formatted_apis = [""]
        for api in apis_to_integrate:
            formatted_apis.append(f"- {api} (gateway-specific API)")
        formatted_apis_str = "\n".join(formatted_apis)

        # Start with base prompt
        complete_prompt = self.get_base_prompt(gateway_name, method, repository_path, standard_branch_name)

        # Add existing PR/branch context if applicable
        if existing_pr_info.get("exists", False):
            complete_prompt += self.get_existing_pr_prompt(existing_pr_info)
        else:
            complete_prompt += self.get_new_branch_prompt(standard_branch_name)

        # Add integrations-specific instructions with documentation path and reference gateway
        complete_prompt += self.get_integrations_specific_prompt(gateway_name, formatted_apis_str, documentation_path,
                                                                 reference_gateway,use_switch)

        # Add retry context if this is a retry iteration
        if is_retry and previous_iterations:
            complete_prompt += self.get_retry_context_prompt(len(previous_iterations) + 1, previous_iterations)

        return complete_prompt 