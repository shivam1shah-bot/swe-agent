"""
QCC Onboarding Service Prompts

This module contains prompt templates for the QCC (Quality Code Coverage) onboarding service.
"""

def create_qcc_implementation_prompt(repo_path: str, repo_name: str, branch_name: str, pr_title: str) -> str:
    """
    Create a comprehensive prompt for the autonomous agent to implement QCC code coverage.
    
    Args:
        repo_path: Repository clone URL
        repo_name: Repository name extracted from URL
        branch_name: Branch name for the implementation
        pr_title: PR title for the implementation
        
    Returns:
        Formatted prompt string for autonomous agent execution
    """
    
    prompt = f"""
You are an expert DevOps engineer specializing in Code Coverage implementation and QCC (Quality Code Coverage) onboarding. You will implement code coverage functionality with graceful shutdown and S3 push capability for Go service repositories.

## INPUT PARAMETERS:
- **Repository**: {repo_path}
- **Repository Name**: {repo_name}
- **Branch Name**: {branch_name}
- **PR Title**: {pr_title}

## STEP 1: Repository Setup and Analysis

### A. Clone Repository
```bash
# Clone the repository using GitHub CLI
gh repo clone {repo_path.replace('https://github.com/', '').replace('.git', '')}
cd {repo_name}
```

### B. Create and Checkout Implementation Branch
```bash
# Create a branch for QCC implementation
BRANCH_NAME="{branch_name}"

# Create and checkout new branch
git checkout -b $BRANCH_NAME
```

### C. Analyze Repository Structure
```bash
# Detect programming language and service type
echo "=== Repository Analysis ==="

if [ -f "go.mod" ]; then
    echo "Go project detected - proceeding with QCC implementation"
    TECH_STACK="Go"
else
    echo "❌ ERROR: Only Go repositories are supported for QCC onboarding"
    echo "This agent only supports Go services with go.mod files"
    echo "Please use a different agent flow for non-Go services"
    exit 1
fi

echo "Detected technology stack: $TECH_STACK"
```

Stop and return the agent execution if not a golang service

## STEP 2: Code Coverage Implementation with Graceful Shutdown and S3 Push

### Objective
Implement code coverage functionality with graceful shutdown and S3 file push capability. This implementation conditionally enables coverage based on branch type and ensures coverage files are properly collected and uploaded during service shutdown.

### 1. GitHub Actions CI Configuration

**Locate the main CI workflow file** (typically `.github/workflows/CI.yml`) and modify the Docker build step:

```yaml
- name: Get Branch
  id: get_branch
  run: |
    echo "BRANCH_NAME=${{github.ref##*/}}" >> $GITHUB_ENV

- name: Build {repo_name} and push image to Harbor
  uses: docker/build-push-action@v2
  with:
    file: ./Dockerfile
    secrets: |
      GIT_TOKEN=${{steps.app-token.outputs.token}}
    build-args: |
      GIT_COMMIT_HASH=${{github.sha}}
      LISTEN_PORT=8080
      GIT_USERNAME=rzp
      BRANCH_NAME=${{env.BRANCH_NAME}}
      CODE_COVERAGE=${{!(env.BRANCH_NAME == 'master' || startsWith(env.BRANCH_NAME, 'hotfix') || startsWith(env.BRANCH_NAME, 'revert'))}}
    push: true
    tags: c.rzp.io/razorpay/{repo_name}:{repo_name}-${{github.sha}}
```

**Key Points:**
- Add `BRANCH_NAME` and `CODE_COVERAGE` to build-args
- `CODE_COVERAGE` is conditionally set to `false` for master, hotfix, and revert branches, `true` for all others
- Ensure the branch name extraction step is added before the build step

### 2. Dockerfile Modifications

**Add the following ARG and ENV declarations** near the top of your Dockerfile:

```dockerfile
# In build stage
ARG BRANCH_NAME
ARG CODE_COVERAGE
ENV CODE_COVERAGE=${{CODE_COVERAGE}}
ENV BRANCH_NAME=${{BRANCH_NAME}}
RUN echo "CODE_COVERAGE is set to (dockerfile) 1 stage: ${{CODE_COVERAGE}}"

# In final stage  
ARG BRANCH_NAME
ARG CODE_COVERAGE
ENV CODE_COVERAGE=${{CODE_COVERAGE}}
ENV BRANCH_NAME=${{BRANCH_NAME}}
RUN echo "CODE_COVERAGE is set to (dockerfile) 2 stage: ${{CODE_COVERAGE}}"
```

**Modify the Go build command** to include the `-cover` flag:

```dockerfile
RUN set -eux && \\
    go generate ./... && \\
    CGO_ENABLED=0 GOOS=linux go build -cover -tags=jsoniter -ldflags "-w -s -X main.AppVersion=$GIT_COMMIT_HASH" -o {repo_name} .
```

**Add coverage directory setup** in the final stage:

```dockerfile
RUN set -eux && \\
    apk update && \\
    apk add --no-cache su-exec tzdata && \\
    mkdir -p /app/conf /app/dockerconf /app/public /app/go-doc /app/coverage && \\
    chmod a+rw /app/coverage && \\
    echo "${{GIT_COMMIT_HASH}}" > /app/public/commit.txt

# Add at the end of Dockerfile
ENV GOCOVERDIR=$WORKDIR/coverage
```

### 3. Entrypoint Script Modifications (`dockerconf/entrypoint.sh`)

**Add the graceful shutdown with S3 push function:**

```bash
init_graceful_shutdown_with_s3_push()
{{
      echo "triggering init_graceful_shutdown_with_s3_push ===>"
      echo "Caught SIGTERM/SIGWINCH signal!"
      echo "Sending sigwinch signal to app"

      kill -s SIGTERM "$APP_PID"
      trap - SIGTERM SIGINT

      # Sleeping for readiness probe to fail so that no new requests are sent to the pod.
      # Time after which readiness probe will start failing.
      READINESS_PROBE_FAIL_SLEEP_TIME=5

      echo "Sleeping for $READINESS_PROBE_FAIL_SLEEP_TIME sec..."
      sleep $READINESS_PROBE_FAIL_SLEEP_TIME

      echo "Sending sigint signal to app"
      wait "$APP_PID"
      sleep 1
      echo "Pushing to S3 via mock"

      # Variables for S3 push
      directory_path="$WORKDIR/coverage"
      server_endpoint="https://mock-go-base.dev.razorpay.in/coverage"
      repo="{repo_name}"
      branch="$BRANCH_NAME"
      commit="$GIT_COMMIT_HASH"
      app_env="$APP_ENV"
      hostname="$HOSTNAME"
      upload_path=""

      for file in "$directory_path"/*
      do
        if [ -f "$file" ]; then
           echo "Sending file: $file"
           response=$(curl -X POST -H "Upload_path: $upload_path" -H "Repo: $repo" -H "Branch: $branch" -H "Commit: $commit" -H "App_env: $app_env" -H "Hostname: $hostname" -F "file=@$file" "$server_endpoint")
           echo "Response: $response"
           echo "S3 push successful"
        fi
      done

      EXIT_STATUS=$?
      return ${{EXIT_STATUS}}
}}
```

**Modify the trap setup** to conditionally use the new function:

```bash
if [[ -z "${{CODE_COVERAGE+x}}" ]]; then
    trap init_graceful_shutdown SIGTERM
else
  if [ "$CODE_COVERAGE" = "true" ]; then
    trap init_graceful_shutdown_with_s3_push SIGTERM SIGINT
  else
    trap init_graceful_shutdown SIGTERM
  fi
fi
```

**Update your service start function** to use APP_PID instead of SERVICE_PID:

```bash
start_{repo_name}()
{{
    echo "Starting {repo_name}"
    su-exec appuser $SRC_DIR/{repo_name} &
    # Get pid for service app
    APP_PID=$!

    # Wait for service to finish. Trap works only on wait.
    wait "$APP_PID"
}}
```

### 4. E2E/Integration Test Configuration

**If your service has E2E tests** (like `.github/workflows/e2e.yml`), add the CODE_COVERAGE parameter:

```yaml
- name: Run E2E Test
  uses: razorpay/e2e-test-orchestrator/e2e-action@master
  with:
    REQUIRED_WORKFLOW_PASS_CHECK: "CI.yml"
    GITHUB_TOKEN: ${{secrets.GITHUB_TOKEN}}
    E2E_ORCHESTRATOR_USERNAME: ${{secrets.E2E_ORCHESTRATOR_USERNAME}}
    E2E_ORCHESTRATOR_PASSWORD: ${{secrets.E2E_ORCHESTRATOR_PASSWORD}}
    CODE_COVERAGE: "true"
```

## STEP 3: Commit Changes and Create PR

```bash
# Create comprehensive implementation guide
cat > QCC_IMPLEMENTATION_GUIDE.md << 'EOF'
# Code Coverage Implementation with Graceful Shutdown and S3 Push - {repo_name}

## Implementation Checklist

- [ ] Add branch name extraction and build arguments to CI workflow
- [ ] Add ARG and ENV declarations for CODE_COVERAGE and BRANCH_NAME in Dockerfile
- [ ] Modify Go build command to include `-cover` flag
- [ ] Create coverage directory and set GOCOVERDIR environment variable
- [ ] Add graceful shutdown with S3 push function to entrypoint.sh
- [ ] Update trap setup to conditionally use new shutdown function
- [ ] Ensure APP_PID is used consistently in service start functions
- [ ] Add CODE_COVERAGE parameter to E2E test workflows (if applicable)
- [ ] Test the implementation with a non-master branch to verify coverage collection
- [ ] Verify graceful shutdown works and files are pushed to S3 on pod termination

## Key Features

1. **Conditional Coverage**: Only enables coverage for non-production branches (excludes master, hotfix, revert)
2. **Graceful Shutdown**: Properly handles SIGTERM/SIGINT signals during pod termination
3. **S3 Integration**: Automatically uploads coverage files to S3 during shutdown
4. **Branch-Aware**: Uses branch name and commit hash for organized coverage file storage
5. **Backward Compatible**: Falls back to standard graceful shutdown when coverage is disabled

## Testing
1. Create a feature branch and push changes
2. Verify CODE_COVERAGE=true is set in CI build
3. Deploy to test environment
4. Generate some traffic to create coverage data
5. Terminate the pod and verify coverage files are uploaded to S3

EOF

# Stage and commit changes
git add QCC_IMPLEMENTATION_GUIDE.md
git add . # Add any modified files

# Commit with descriptive message
git commit -m "feat: Add QCC Code Coverage Implementation with Graceful Shutdown and S3 Push

- Add conditional code coverage based on branch type
- Implement graceful shutdown with S3 coverage file upload
- Modify CI/CD pipeline for coverage build arguments
- Update Dockerfile with coverage configuration
- Enhance entrypoint script with coverage-aware shutdown

Service: {repo_name}
Branch: {branch_name}
Coverage enabled for: non-master, non-hotfix, non-revert branches

Generated by SWE Agent QCC Onboarding Service"

# Push the implementation branch
git push -u origin $BRANCH_NAME

# Create PR using GitHub CLI
gh pr create \\
  --title "{pr_title}" \\
  --body "## QCC Code Coverage Implementation Summary

This PR implements code coverage functionality with graceful shutdown and S3 push capability for **{repo_name}**.

## 🔧 Implementation Details

### Key Features
- **Conditional Coverage**: Only enabled for non-production branches (excludes master, hotfix, revert)
- **Graceful Shutdown**: Handles SIGTERM/SIGINT signals during pod termination
- **S3 Integration**: Automatically uploads coverage files to S3 during shutdown
- **Branch-Aware**: Uses branch name and commit hash for organized storage
- **Backward Compatible**: Falls back to standard shutdown when coverage disabled

### Changes Included
1. **GitHub Actions CI**: Added branch extraction and CODE_COVERAGE build argument
2. **Dockerfile**: Modified with coverage build flags and directory setup
3. **Entrypoint Script**: Enhanced with coverage-aware graceful shutdown
4. **E2E Tests**: Updated with coverage parameters (if applicable)

## 📊 Implementation Checklist
- [ ] Integrate CI workflow modifications
- [ ] Apply Dockerfile coverage configuration
- [ ] Update entrypoint script with new shutdown function
- [ ] Test coverage collection on non-master branch
- [ ] Verify S3 upload during pod termination
- [ ] Validate backward compatibility

**Generated by**: SWE Agent QCC Onboarding Service  
**Service**: {repo_name}  
**Implementation Date**: $(date)" \\
  --draft
```

## VALIDATION CHECKLIST:
- ✅ Repository successfully cloned and analyzed
- ✅ Go service validated (go.mod found)
- ✅ CI workflow modifications implemented
- ✅ Dockerfile coverage configuration added
- ✅ Entrypoint script enhanced with S3 push capability
- ✅ E2E test configuration updated (if applicable)
- ✅ Implementation guide created
- ✅ Changes committed with descriptive messages
- ✅ PR created with implementation checklist

## IMPORTANT: Final Report Commit
After completing all implementation tasks, it is **CRITICAL** to commit the final results and implementation details to the report repository. This ensures proper tracking, documentation, and audit trail for the QCC onboarding process.

```bash
# IMPORTANT: Commit to report repository before ending work
echo "🔄 Committing implementation results to report repository..."
# This step is essential for tracking and auditing QCC onboarding implementations
```

Execute this QCC implementation workflow to add production-ready code coverage with graceful shutdown and S3 integration to the Go service repository.
"""

    return prompt 