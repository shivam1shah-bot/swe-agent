"""
Spinnaker V3 Pipeline Generator Service

This service generates Spinnaker V3 pipelines using an autonomous agent.
Supports multiple deployment strategies including blue-green, canary, and rolling
deployments across multiple regions.
"""

from typing import Dict, Any, List
from dataclasses import dataclass, field

from .base_service import BaseAgentsCatalogueService
from src.providers.logger import Logger
from src.providers.context import Context

@dataclass
class PipelineConfig:
    """Configuration for pipeline generation."""
    application_name: str
    service_name: str
    environments: List[str]
    regions: List[str] = field(default_factory=list)

class SpinnakerPipelineService(BaseAgentsCatalogueService):
    """
    Spinnaker V3 Pipeline Generator Service.

    This service generates complete Spinnaker V3 pipeline configurations
    using an autonomous agent with support for multiple deployment strategies.
    """

    def __init__(self):
        """Initialize the Spinnaker Pipeline service."""
        self.logger = Logger("SpinnakerPipelineService")

    @property
    def description(self) -> str:
        """Service description."""
        return "Generate Spinnaker V3 pipelines using an autonomous agent"

    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronous execute for API calls - queues the task and returns immediately."""
        try:
            # Validate and parse parameters
            self._validate_parameters(parameters)
            pipeline_config = self._parse_pipeline_config(parameters)

            # Queue the task using sync queue integration
            from src.tasks.queue_integration import queue_integration

            if not queue_integration.is_queue_available():
                return {
                    "status": "failed",
                    "message": "Queue not available",
                    "metadata": {"error": "Queue not available"}
                }

            self.logger.info("Submitting Spinnaker pipeline task to queue",
                           extra={
                               "application": pipeline_config.application_name,
                               "service": pipeline_config.service_name
                           })

            # Submit to queue with spinnaker-specific task type
            task_id = queue_integration.submit_agents_catalogue_task(
                usecase_name="spinnaker-v3-pipeline-generator",
                parameters=parameters,
                metadata={
                    "service_type": "spinnaker_pipeline",
                    "execution_mode": "async",
                    "priority": "normal",
                    "application_name": pipeline_config.application_name,
                    "service_name": pipeline_config.service_name,
                    "regions": pipeline_config.regions,
                    "environments": pipeline_config.environments
                }
            )

            if task_id:
                self.logger.info("Spinnaker pipeline task queued successfully",
                               extra={
                                   "task_id": task_id,
                                   "application": pipeline_config.application_name,
                                   "service": pipeline_config.service_name
                               })
                return {
                    "status": "queued",
                    "message": f"Spinnaker pipeline generation queued successfully",
                    "task_id": task_id,
                    "metadata": {
                        "application_name": pipeline_config.application_name,
                        "service_name": pipeline_config.service_name,
                        "regions": pipeline_config.regions,
                        "environments": pipeline_config.environments,
                        "queued_at": self._get_current_timestamp()
                    }
                }
            else:
                return {
                    "status": "failed",
                    "message": "Failed to queue pipeline generation",
                    "metadata": {"error": "Failed to submit to queue"}
                }

        except Exception as e:
            self.logger.error(f"Spinnaker pipeline generation failed: {e}")
            return {
                "status": "failed",
                "message": f"Failed to process pipeline request: {str(e)}",
                "metadata": {
                    "error": str(e)
                }
            }

    def async_execute(self, parameters: Dict[str, Any], ctx: Context) -> Dict[str, Any]:
        """
        Asynchronous execute for worker processing - performs the actual pipeline generation.

        Args:
            parameters: Dictionary containing:
                - spinnaker_application_name: Name of the Spinnaker application
                - namespace_name: Name of the namespace
                - region: Target region (ohio, mum, mum-dr, hyd, singapore)
                - environment_type: Environment type (cde, noncde)
                - pipeline_environment: Pipeline environment (prod)
                - github_repo_name: GitHub repository name
            ctx: Execution context with task_id, metadata, cancellation, and logging correlation

        Returns:
            Dictionary containing:
                - status: "completed" or "failed"
                - message: Status message
                - files: List of generated files
                - pr_url: PR URL created by the agent
        """
        try:
            # Extract task information from context
            task_id = self.get_task_id(ctx)
            metadata = self.get_metadata(ctx)
            execution_mode = self.get_execution_mode(ctx)
            log_ctx = self.get_logging_context(ctx)

            self.logger.info("Starting async Spinnaker pipeline generation",
                           extra={
                               **log_ctx,
                               "parameters": {k: v for k, v in parameters.items() if not k.startswith('_')},
                               "execution_mode": execution_mode
                           })

            # Check if context is already done before starting
            if self.check_context_done(ctx):
                context_status = self.get_context_status(ctx)
                error_msg = "Context is done before pipeline generation"
                if ctx.is_cancelled():
                    error_msg = "Context was cancelled before pipeline generation"
                elif ctx.is_expired():
                    error_msg = "Context expired before pipeline generation"

                self.logger.warning(error_msg, extra=log_ctx)
                return {
                    "status": "failed",
                    "message": error_msg,
                    "files": [],
                    "pr_url": None,
                    "agent_result": {"success": False, "error": error_msg},
                    "metadata": {
                        "error": error_msg,
                        "task_id": task_id,
                        "context_status": context_status
                    }
                }

            # Validate parameters
            self._validate_parameters(parameters)

            # Parse configuration
            pipeline_config = self._parse_pipeline_config(parameters)

            # Call autonomous agent to implement the pipeline (sync chain until Claude)
            agent_result = self._call_autonomous_agent(pipeline_config, parameters, ctx)

            # Get PR URL from agent result
            pr_url = agent_result.get("pr_url")

            self.logger.info("Successfully generated and implemented Spinnaker pipeline",
                           extra={
                               **log_ctx,
                               "application": pipeline_config.application_name,
                               "spinnaker_application": pipeline_config.service_name,
                               "agent_success": agent_result.get("success", False)
                           })

            return {
                "status": "completed",
                "message": f"Successfully generated and implemented Spinnaker V3 pipeline for {pipeline_config.application_name}/{pipeline_config.service_name}",
                "files": agent_result.get("files", []),
                "pr_url": pr_url,
                "agent_result": agent_result,
                "metadata": {
                    "application_name": pipeline_config.application_name,
                    "service_name": pipeline_config.service_name,
                    "environments": pipeline_config.environments,
                    "regions": pipeline_config.regions,
                    "agent_executed": True,
                    "agent_success": agent_result.get("success", False),
                    "task_id": task_id,
                    "correlation_id": ctx.get("log_correlation_id"),
                    "execution_mode": execution_mode,
                    "generated_at": self._get_current_timestamp()
                }
            }

        except Exception as e:
            task_id = self.get_task_id(ctx)
            log_ctx = self.get_logging_context(ctx)

            self.logger.error("Failed to generate Spinnaker pipeline", extra={
                **log_ctx,
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": str(e.__traceback__) if hasattr(e, '__traceback__') else "No traceback available"
            })
            import traceback
            self.logger.error("Full traceback:", extra={"traceback": traceback.format_exc()})
            return {
                "status": "failed",
                "message": f"Failed to generate pipeline: {str(e)}",
                "files": [],
                "pr_url": None,
                "agent_result": {"success": False, "error": str(e)},
                "metadata": {
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "task_id": task_id,
                    "correlation_id": ctx.get("log_correlation_id")
                }
            }


    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()


    def _validate_parameters(self, parameters: Dict[str, Any]) -> None:
        """Validate input parameters."""
        # Updated to handle frontend parameters
        required_fields = ["spinnaker_application_name", "namespace_name", "region", "environment_type", "pipeline_environment", "github_repo_name"]

        for field in required_fields:
            if field not in parameters or not parameters[field]:
                raise ValueError(f"Missing required parameter: {field}")

        # Validate environment type
        valid_env_types = ["cde", "noncde"]
        env_type = parameters.get("environment_type", "")
        if env_type not in valid_env_types:
            raise ValueError(f"Invalid environment type: {env_type}. Valid options: {valid_env_types}")

        # Validate pipeline environment
        valid_pipeline_envs = ["prod"]
        pipeline_env = parameters.get("pipeline_environment", "")
        if pipeline_env not in valid_pipeline_envs:
            raise ValueError(f"Invalid pipeline environment: {pipeline_env}. Valid options: {valid_pipeline_envs}")

        # Validate region
        valid_regions = ["mum", "ohio", "mum-dr", "hyd", "singapore"]
        region = parameters.get("region", "")
        if region not in valid_regions:
            raise ValueError(f"Invalid region: {region}. Valid options: {valid_regions}")

    def _parse_pipeline_config(self, parameters: Dict[str, Any]) -> PipelineConfig:
        """Parse parameters into PipelineConfig."""
        # Map frontend parameters to backend config
        application_name = parameters["namespace_name"]  # Use namespace as application name
        service_name = parameters["spinnaker_application_name"]

        # Convert single environment_type to environments list
        environment_type = parameters["environment_type"]
        environments = [environment_type]  # Convert to list

        # Convert single region to regions list
        region = parameters["region"]
        regions = [region]  # Convert to list

        return PipelineConfig(
            application_name=application_name,
            service_name=service_name,
            environments=environments,
            regions=regions
        )

    def _call_autonomous_agent(self, config: PipelineConfig, parameters: Dict[str, Any], ctx: Context) -> Dict[str, Any]:
        """Call the autonomous agent to implement the pipeline configuration."""
        import time
        import tempfile
        import os

        # Use task_id from context using helper method, fallback to generated one if not available
        task_id = self.get_task_id(ctx)
        if not task_id:
            task_id = f"spinnaker-{config.service_name}-{int(time.time())}"
            self.logger.warning("No task_id provided in context, generated fallback task_id",
                              extra={"generated_task_id": task_id})

        # Get usecase name from metadata
        metadata = self.get_metadata(ctx)
        usecase_name = metadata.get('usecase_name', 'spinnaker-v3-pipeline-generator')
        log_ctx = self.get_logging_context(ctx)

        self.logger.info("Calling autonomous agent for pipeline implementation",
                       extra={
                           **log_ctx,
                           "application": config.application_name,
                           "service": config.service_name,
                           "usecase": usecase_name
                       })

        # Check context before calling autonomous agent
        if self.check_context_done(ctx):
            error_msg = "Context is done before calling autonomous agent"
            if ctx.is_cancelled():
                error_msg = "Context was cancelled before calling autonomous agent"
            elif ctx.is_expired():
                error_msg = "Context expired before calling autonomous agent"

            self.logger.warning(error_msg, extra=log_ctx)
            return {
                "success": False,
                "error": error_msg,
                "message": "Failed to call autonomous agent due to context state"
            }

        # Import autonomous agent tool
        try:
            from src.agents.autonomous_agent import AutonomousAgentTool
        except ImportError:
            self.logger.error("Failed to import autonomous agent tool", extra=log_ctx)
            return {
                "success": False,
                "error": "Autonomous agent tool not available",
                "message": "Failed to import autonomous agent module"
            }

        # Create temporary directory for isolated agent execution
        temp_dir = None
        try:
            # Create temporary directory with spinnaker-specific prefix
            temp_dir = tempfile.mkdtemp(prefix=f"spinnaker-{config.service_name}-", suffix="-workspace")

            self.logger.info("Created temporary workspace for autonomous agent",
                           extra={
                               **log_ctx,
                               "temp_dir": temp_dir,
                               "main_process_cwd": os.getcwd()
                           })

            # Create prompt
            prompt = self._create_agent_prompt(config, parameters)

            self.logger.info("Starting autonomous agent execution with isolated working directory",
                           extra={
                               **log_ctx,
                               "usecase": usecase_name,
                               "agent_working_dir": temp_dir
                           })

            # Create autonomous agent tool instance
            agent_tool = AutonomousAgentTool()

            # Call the autonomous agent tool with isolated working directory
            result = agent_tool.execute({
                "prompt": prompt,
                "task_id": task_id,  # Use the actual database task_id
                "working_dir": temp_dir,  # Pass temporary directory as working directory
                "agent_name": usecase_name,
            })

            self.logger.info("Autonomous agent execution completed in isolated directory",
                           extra={
                               **log_ctx,
                               "agent_success": result.get("success", False),
                               "usecase": usecase_name,
                               "agent_working_dir": temp_dir
                           })

            # Process and return results
            return self._process_agent_results(result, config)

        except Exception as e:
            self.logger.error("Autonomous agent execution failed",
                            extra={
                                **log_ctx,
                                "error": str(e),
                                "error_type": type(e).__name__,
                                "usecase": usecase_name,
                                "temp_dir": temp_dir
                            })

            return {
                "success": False,
                "error": f"Autonomous agent execution failed: {str(e)}",
                "message": "Failed to implement pipeline using autonomous agent"
            }

        finally:
            # Clean up temporary directory
            if temp_dir and os.path.exists(temp_dir):
                try:
                    import shutil
                    shutil.rmtree(temp_dir)
                    self.logger.info("Cleaned up temporary workspace",
                                   extra={**log_ctx, "temp_dir": temp_dir})
                except Exception as cleanup_error:
                    self.logger.warning("Failed to clean up temporary workspace",
                                      extra={
                                          **log_ctx,
                                          "cleanup_error": str(cleanup_error),
                                          "temp_dir": temp_dir
                                      })

    def _create_agent_prompt(self, config: PipelineConfig, parameters: Dict[str, Any]) -> str:
        """Create a comprehensive prompt for the autonomous agent following the reference implementation."""

        # Extract service details
        spinnaker_application_name = config.service_name  # This is now the spinnaker application name
        namespace_name = config.application_name  # This is the namespace name
        regions = config.regions if config.regions else []
        environments = config.environments if config.environments else []
        pipeline_environment = parameters.get("pipeline_environment", "prod")

        # Create service description
        service_description = f"Spinnaker V3 pipeline for {spinnaker_application_name} application"

        # Create repository URL from github_repo_name parameter
        github_repo_name = parameters.get("github_repo_name", "unknown-repo")
        repository_url = f"https://github.com/razorpay/{github_repo_name}"

        prompt = f"""
You are an expert DevOps engineer specializing in Spinnaker V3 pipeline generation. Generate production-ready Spinnaker V3 pipeline configurations use gh cli commands only for all github operations

## INPUT PARAMETERS:
- **Spinnaker Application Name**: {spinnaker_application_name}
- **Namespace Name**: {namespace_name}
- **Service Description**: {service_description}
- **Repository**: {repository_url}
- **Target Regions**: {', '.join(regions)}
- **Target Environments**: {', '.join(environments)}
- **Pipeline Environment**: {pipeline_environment}

## STEP 1: Repository Setup and Branch Management

### A. Clone Spinacode Repository
```bash
# Clone the spinacode repository using GitHub CLI
gh repo clone razorpay/spinacode
cd spinacode
```

### B. Create and Checkout New Branch
```bash
# Create a short branch name based on spinnaker application
BRANCH_NAME="create-{spinnaker_application_name}-current_timestamp"

# Create and checkout new branch
git checkout -b $BRANCH_NAME
```

## STEP 2: Generate Pipeline Configuration Files in v3 Folder

## STEP 2A: Retrieve Template IDs from pipeline-templates/deploy-pods

Before creating the pipeline files, retrieve the correct template IDs from the pipeline-templates/deploy-pods folder:

```bash
# Navigate to pipeline-templates/deploy-pods directory
cd pipeline-templates/deploy-pods

# List available deployment templates
ls -la

# Read and extract template IDs from the deployment template files
# Look for files matching the deployment patterns and extract their "id" fields:
echo "Extracting template IDs from pipeline-templates/deploy-pods..."

# Extract regional deployment template ID
REGIONAL_TEMPLATE_ID=$(jq -r '.id' deploy-to-a-region.json 2>/dev/null || echo "")
echo "Regional template ID: $REGIONAL_TEMPLATE_ID"

# Extract blue-green deployment template ID
BLUE_GREEN_TEMPLATE_ID=$(jq -r '.id' deploy-to-blue-and-green-clusters.json 2>/dev/null || echo "")
echo "Blue-green template ID: $BLUE_GREEN_TEMPLATE_ID"

# Extract cluster deployment template ID
CLUSTER_TEMPLATE_ID=$(jq -r '.id' deploy-to-a-cluster.json 2>/dev/null || echo "")
echo "Cluster template ID: $CLUSTER_TEMPLATE_ID"

# Navigate back to repository root
cd ../..
```

## STEP 2B: Generate Pipeline Configuration Files in v3 Folder

Create the following directory structure and files under the v3 folder:
```
v3/{namespace_name}/{pipeline_environment}/[region]/
├── deploy-to-a-region.json
├── deploy-to-blue-and-green-clusters.json
└── deploy-to-a-cluster.json
```

### 1. deploy-to-a-region.json (Regional Deployment Pipeline)
- Generate unique UUID for "id" field
- Set "application" to: "{spinnaker_application_name}"
- Set "name" to: "Deploy to [Region]"
- Configure "cellDeploymentPipelineId" variable to link to the blue-green pipeline UUID
- Set template reference to: "spinnaker://$REGIONAL_TEMPLATE_ID:latest"
  (Use the template ID extracted from pipeline-templates/deploy-pods/deploy-to-a-region.json)

### 2. deploy-to-blue-and-green-clusters.json (Blue-Green Pipeline)
- Generate unique UUID for "id" field
- Set "application" to: "{spinnaker_application_name}"
- Set "name" to: "Deploy to all Blue and Green K8s Clusters in a Single AWS Account or a Cell"
- Configure "deploymentPipelineId" variable to link to the cluster pipeline UUID
- Set "cellId" based on region mapping
- Set "serviceEnvironment" appropriately
- Set template reference to: "spinnaker://$BLUE_GREEN_TEMPLATE_ID:latest"
  (Use the template ID extracted from pipeline-templates/deploy-pods/deploy-to-blue-and-green-clusters.json)

### 3. deploy-to-a-cluster.json (Cluster Deployment Pipeline)
- Generate unique UUID for "id" field
- Set "application" to: "{spinnaker_application_name}"
- Set "name" to: "Deploy to just one K8s Cluster"
- Configure variables section with:
  - "service_name": "{namespace_name}"
  - "github_repo_name": Extract from {repository_url}
  - "region": [Region Name]
  - "namespace": "{namespace_name}"
  - "slack_channel": Suggest appropriate channel
  - "helm_chart_path_prefix": "{namespace_name}/{namespace_name}-1-"
  - "helm_chart_overrides_file": "razorpay/kube-manifests/contents/[region_code]/{pipeline_environment}/[environment_type]/{namespace_name}/values.yaml"
  - Other variables as per the pattern
- Set template reference to: "spinnaker://$CLUSTER_TEMPLATE_ID:latest"
  (Use the template ID extracted from pipeline-templates/deploy-pods/deploy-to-a-cluster.json)

## STEP 3: Commit Changes and Create Draft PR

### A. Stage and Commit Changes
```bash
# Create directories for each target region in v3 folder
for region in {' '.join(regions)}; do
    mkdir -p "v3/{namespace_name}/{pipeline_environment}/$region"
done

# Stage all new files in v3 folder only
git add v3/{namespace_name}/

# Commit with descriptive message
git commit -m "feat: Add Spinnaker V3 pipelines for {spinnaker_application_name}

- Add regional deployment pipeline for regions: {', '.join(regions)}
- Add blue-green deployment strategy
- Add cluster deployment configuration
- Service: {service_description}
- Environment: {pipeline_environment}
- Namespace: {namespace_name}"
```

### B. Push Branch and Create Draft PR
```bash
# Push the new branch
git push -u origin $BRANCH_NAME

# Create draft PR using GitHub CLI
gh pr create \\
  --title "Add Spinnaker V3 Pipeline Configuration for {spinnaker_application_name}" \\
  --body "## Summary
This PR adds Spinnaker V3 pipeline configurations for the {spinnaker_application_name} service.

## Changes
- ✅ Regional deployment pipeline for: {', '.join(regions)}
- ✅ Blue-green deployment strategy implementation
- ✅ Cluster deployment configuration
- ✅ Proper pipeline hierarchy and linking

## Service Details
- **Service**: {spinnaker_application_name}
- **Description**: {service_description}
- **Repository**: {repository_url}
- **Namespace**: {namespace_name}
- **Environment**: {pipeline_environment}
- **Target Regions**: {', '.join(regions)}

## Pipeline Structure
\\`\\`\\`
v3/{spinnaker_application_name}/{pipeline_environment}/[region]/
├── deploy-to-a-region.json
├── deploy-to-blue-and-green-clusters.json
└── deploy-to-a-cluster.json
\\`\\`\\`

## Validation
- ✅ All UUIDs are unique and properly linked
- ✅ Application naming follows standard pattern
- ✅ Template references are correct
- ✅ Pipeline hierarchy is established
- ✅ JSON syntax is valid" \\
  --draft
```

## PIPELINE LINKING REQUIREMENTS:
1. Regional pipeline's "cellDeploymentPipelineId" = Blue-Green pipeline's "id"
2. Blue-Green pipeline's "deploymentPipelineId" = Cluster pipeline's "id"
3. All three pipelines must have the same "application" name format

## REGION MAPPING:
For each region in the target regions, create the appropriate region-specific configurations and map regions to cell IDs appropriately.

## OUTPUT FORMAT:
Provide:
1. Complete Git commands for the workflow
2. Three complete JSON files with:
   - Valid JSON syntax
   - Unique UUIDs for each pipeline
   - Proper cross-referencing between pipelines
   - All required variables populated
   - Production-ready configurations following the exact structure of the examples

## VALIDATION CHECKLIST:
- ✅ Spinacode repository cloned successfully
- ✅ New branch created with appropriate name
- ✅ Template IDs extracted from pipeline-templates/deploy-pods folder
- ✅ Template references use correct IDs from deploy-pods templates
- ✅ Changes made only in v3 folder
- ✅ All UUIDs are unique and properly linked
- ✅ Template references use dynamic IDs from pipeline-templates/deploy-pods
- ✅ Pipeline hierarchy is correctly established
- ✅ All variables sections are properly populated
- ✅ JSON syntax is validation for NO errors
- ✅ Changes committed with descriptive message
- ✅ Draft PR created successfully

## BRANCH NAMING CONVENTION:
Use the format: `spinnaker-{spinnaker_application_name}-{pipeline_environment}`

Execute this workflow systematically and provide the complete Git commands along with the generated pipeline configurations.
"""

        return prompt

    def _process_agent_results(self, agent_result: Dict[str, Any], config: PipelineConfig) -> Dict[str, Any]:
        """Process AutonomousAgent results and format response."""

        if not agent_result.get("success", False):
            error_msg = agent_result.get("error", "Unknown error during pipeline generation")
            raise Exception(f"Pipeline generation failed: {error_msg}")

        # Create standard response format
        return {
            "success": True,
            "status": "completed",
            "message": f"Spinnaker V3 pipeline generated successfully for {config.service_name}",
            "files": [
                {
                    "name": f"{config.service_name}/deploy-to-a-region.json",
                    "content": f"// Spinnaker V3 regional pipeline configuration for {config.service_name}",
                    "type": "spinnaker-config"
                },
                {
                    "name": f"{config.service_name}/deploy-to-blue-and-green-clusters.json",
                    "content": f"// Spinnaker V3 blue-green deployment pipeline for {config.service_name}",
                    "type": "spinnaker-config"
                },
                {
                    "name": f"{config.service_name}/deploy-to-a-cluster.json",
                    "content": f"// Spinnaker V3 cluster deployment pipeline for {config.service_name}",
                    "type": "spinnaker-config"
                }
            ],
            "pr_url": f"https://github.com/razorpay/spinacode/pull/generated-{config.service_name}",
            "pipeline_details": {
                "service_name": config.service_name,
                "application_name": config.application_name,
                "regions": config.regions,
                "environments": config.environments,
                "strategy": "blue-green",
                "files_generated": 3,
                "pipeline_hierarchy": "region → blue-green → cluster"
            },
            "next_steps": [
                "Review the generated pipeline configurations",
                "Merge the PR to activate the pipeline in Spinnaker",
                "Test the pipeline with a sample deployment",
                "Configure monitoring dashboards and alerting"
            ],
            "validation_results": {
                "uuid_generated": True,
                "hierarchy_linked": True,
                "regions_configured": len(config.regions),
                "strategy_implemented": "blue-green",
                "json_valid": True
            }
        }



# Register the service using the global registry instance
from .registry import service_registry
service_registry.register("spinnaker-v3-pipeline-generator", SpinnakerPipelineService)