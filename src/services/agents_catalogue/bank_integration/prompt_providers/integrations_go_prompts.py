"""
Integrations-Go Prompt Provider

Contains prompts and prompt building logic for integrations-go bank integration.
These prompts are extracted from the original server1.py file.
"""

from typing import Dict, Any, List, Optional


class IntegrationsGoPromptProvider:
    """Prompt provider for integrations-go bank integration."""
    
    def __init__(self):
        """Initialize the prompt provider."""
        pass
    
    def build_complete_prompt(self, 
                             bank_name: str,
                             version: str,
                             branch_name: str,
                             reference_files: Optional[Dict[str, str]] = None,
                             **kwargs) -> str:
        """
        Build complete prompt for integrations-go bank integration.
        
        Args:
            bank_name: Name of the bank to integrate
            version: Version of the integration
            branch_name: Git branch name to use
            reference_files: Reference files and their content
            **kwargs: Additional parameters
            
        Returns:
            Complete prompt for integrations-go integration
        """
        
        # Base prompt extracted from server1.py
        base_prompt = f"""
You are an expert Go developer working on a bank integration project for {bank_name.upper()} bank.

## Task Overview
Integrate {bank_name.upper()} bank into the integrations-go repository with the following requirements:

### Repository Details
- Repository: integrations-go
- Branch: {branch_name}
- Bank Name: {bank_name.upper()}
- Version: {version}

### Integration Requirements
1. Create comprehensive Go code for {bank_name.upper()} bank integration
2. Follow existing patterns and architecture from other banks
3. Implement all required APIs and endpoints
4. Add proper error handling and validation
5. Include comprehensive unit tests
6. Follow Go best practices and conventions

### Code Generation Instructions
1. **Analyze Repository Structure**: Study the existing codebase to understand patterns
2. **Create Bank Package**: Create new package for {bank_name.lower()} bank
3. **Implement Core Files**: 
   - Gateway configuration
   - Request/response models
   - API handlers
   - Error mappings
   - Constants and configurations
4. **Add Unit Tests**: Comprehensive test coverage for all new code
5. **Update Configurations**: Add bank to relevant configuration files
6. **Create Documentation**: Add README and API documentation

### Quality Standards
- All code must compile without errors
- Unit tests must pass with >90% coverage
- Follow existing code patterns and conventions
- Include proper logging and monitoring
- Handle all edge cases and error scenarios

### Completion Checklist
- [ ] Bank package created with all required files
- [ ] All APIs implemented and tested  
- [ ] Unit tests added with >90% coverage
- [ ] Configuration files updated
- [ ] Documentation added
- [ ] Code passes linting and formatting checks
- [ ] Integration follows existing patterns

Please implement the complete integration following these requirements.
"""
        
        # Add reference context if provided
        if reference_files:
            base_prompt += "\n\n### Reference Files\n"
            for file_name, content in reference_files.items():
                base_prompt += f"\n**{file_name}:**\n```\n{content[:2000]}...\n```\n"
        
        return base_prompt
    
    def get_unit_test_prompt(self, bank_name: str, files_created: List[str]) -> str:
        """
        Get prompt for generating unit tests.
        
        Args:
            bank_name: Name of the bank
            files_created: List of files that were created
            
        Returns:
            Unit test generation prompt
        """
        return f"""
Generate comprehensive unit tests for the {bank_name.upper()} bank integration.

### Files to Test
{chr(10).join(f'- {file}' for file in files_created)}

### Test Requirements
1. **Coverage**: Achieve >90% test coverage
2. **Test Types**: Unit tests, integration tests, error cases
3. **Mocking**: Mock external dependencies appropriately  
4. **Assertions**: Comprehensive assertions for all scenarios
5. **Edge Cases**: Test boundary conditions and error paths

### Test Structure
- Follow existing test patterns in the repository
- Use testify/suite for test organization
- Include setup and teardown methods
- Test both success and failure scenarios

Please generate all necessary test files with comprehensive coverage.
"""
    
    def get_validation_prompt(self, bank_name: str) -> str:
        """
        Get prompt for validating generated code.
        
        Args:
            bank_name: Name of the bank
            
        Returns:
            Validation prompt
        """
        return f"""
Validate the {bank_name.upper()} bank integration implementation.

### Validation Checklist
1. **Code Compilation**: All Go code compiles without errors
2. **Test Execution**: All tests pass successfully
3. **Linting**: Code passes go vet and golangci-lint
4. **Dependencies**: All imports are resolved correctly
5. **Patterns**: Code follows repository conventions
6. **Error Handling**: Proper error handling implemented
7. **Documentation**: Adequate code comments and docs

Please run all validation checks and report any issues found.
"""


