# SWE-Agent Compact System Management
PROJECT_NAME := swe-agent
VERSION := $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")

# Get UI port from UI environment config using shared function (falls back to 8001)
APP_ENV := $(or $(APP_ENV),dev_docker)
UI_PORT := $(shell bash -c 'source commands/lib/get_ui_port.sh && APP_ENV=$(APP_ENV) get_ui_port')

# Colors
GREEN := \033[32m
YELLOW := \033[33m
CYAN := \033[36m
RED := \033[31m
RESET := \033[0m

# Shared command snippets (DRY)
CHECK_YARN := if ! command -v yarn &> /dev/null; then \
		echo "$(RED)Error: yarn is not available.$(RESET)"; \
		echo "Yarn is required (managed via Corepack)."; \
		echo "Enable Corepack: corepack enable"; \
		exit 1; \
	fi
YARN_INSTALL := cd ui && yarn install --immutable
UI_DEV_SERVER := cd ui && PORT=$(UI_PORT) yarn dev

.DEFAULT_GOAL := help

##@ Quick Commands

.PHONY: help
help: ## Display this help
	@echo "$(CYAN)SWE-Agent System$(RESET)"
	@echo "$(CYAN)=================$(RESET)"
	@awk 'BEGIN {FS = ":.*##"; printf "Usage:\n  make $(CYAN)<target>$(RESET)\n"} /^[a-zA-Z_0-9-]+:.*?##/ { printf "  $(CYAN)%-15s$(RESET) %s\n", $$1, $$2 } /^##@/ { printf "\n$(YELLOW)%s$(RESET)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Docker Services

.PHONY: start
start: ## 🚀 Start all services (one-command setup)
	@echo "$(GREEN)Starting SWE-Agent system...$(RESET)"
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml up -d --remove-orphans
	@sleep 5
	@$(MAKE) status

.PHONY: stop
stop: ## 🛑 Stop all services
	@echo "$(GREEN)Stopping all services...$(RESET)"
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml down

.PHONY: restart
restart: ## 🔄 Restart app containers only (API, UI, workers, MCP, webhooks) - keeps infrastructure running
	@echo "$(GREEN)Restarting app containers (API, UI, workers, MCP, webhooks)...$(RESET)"
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml restart swe-agent-api swe-agent-ui swe-agent-task-execution-worker swe-agent-code-review-worker swe-agent-mcp-server swe-agent-webhook-receiver
	@sleep 3
	@$(MAKE) status

.PHONY: restart-all
restart-all: stop start ## 🔄 Restart all services (including DB, Redis, LocalStack)

.PHONY: run
run: ## 🏃 Build and start all services
	@echo "$(GREEN)Building and starting SWE-Agent system...$(RESET)"
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml build
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml up -d
	@sleep 5
	@$(MAKE) status

.PHONY: build
build: ## 🔨 Build all images
	@echo "$(GREEN)Building all images (including base backend)...$(RESET)"
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml build --parallel

.PHONY: build-base-backend
build-base-backend: ## 🔨 Build shared backend base image (optional - docker-compose handles this)
	@echo "$(GREEN)Building shared backend base image...$(RESET)"
	@docker build -f build/docker/dev/Dockerfile.base-backend.dev -t razorpay/swe-agent-base-backend:dev .

.PHONY: build-backend-services
build-backend-services: ## 🔨 Build API, Worker, and MCP (base image built automatically)
	@echo "$(GREEN)Building backend services (base image included)...$(RESET)"
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml build swe-agent-base-backend swe-agent-api swe-agent-task-execution-worker swe-agent-mcp-server

.PHONY: build-ui
build-ui: ## 🎨 Build UI image only
	@echo "$(GREEN)Building UI image...$(RESET)"
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml build swe-agent-ui

.PHONY: build-api
build-api: ## 🔧 Build API image only
	@echo "$(GREEN)Building API image...$(RESET)"
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml build swe-agent-api

.PHONY: build-worker
build-worker: ## 👷 Build Worker image only
	@echo "$(GREEN)Building Worker image...$(RESET)"
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml build swe-agent-task-execution-worker

.PHONY: build-review-worker
build-review-worker: ## 📝 Build Code Review Worker image only
	@echo "$(GREEN)Building Code Review Worker image...$(RESET)"
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml build swe-agent-code-review-worker

.PHONY: build-mcp-server
build-mcp-server: ## 🔗 Build MCP Server image only
	@echo "$(GREEN)Building MCP Server image...$(RESET)"
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml build swe-agent-mcp-server

.PHONY: build-webhook-receiver
build-webhook-receiver: ## 🔔 Build Webhook Receiver image only
	@echo "$(GREEN)Building Webhook Receiver image...$(RESET)"
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml build swe-agent-webhook-receiver

.PHONY: rebuild
rebuild: ## 🔨 Rebuild (with cache) and restart
	@echo "$(GREEN)Rebuilding services (using cache)...$(RESET)"
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml down
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml build --parallel
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml up -d

.PHONY: rebuild-no-cache
rebuild-no-cache: ## 🔨 Rebuild (no cache) and restart - use after Dockerfile changes
	@echo "$(GREEN)Rebuilding services (no cache)...$(RESET)"
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml down
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml build --no-cache --parallel
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml up -d

.PHONY: status
status: ## 📊 Show system status
	@echo "$(CYAN)System Status$(RESET)"
	@echo "$(CYAN)==============$(RESET)"
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml ps
	@echo "\n$(YELLOW)Health Check:$(RESET)"
	@curl -s http://localhost:28002/api/v1/health >/dev/null 2>&1 && echo "  API Server: $(GREEN)✅$(RESET)" || echo "  API Server: ❌"
	@curl -s http://localhost:28003/health >/dev/null 2>&1 && echo "  MCP Server: $(GREEN)✅$(RESET)" || echo "  MCP Server: ❌"
	@curl -s http://localhost:28004/health >/dev/null 2>&1 && echo "  Webhook Receiver: $(GREEN)✅$(RESET)" || echo "  Webhook Receiver: ❌"
	@curl -s http://localhost:4566/_localstack/health >/dev/null 2>&1 && echo "  LocalStack: $(GREEN)✅$(RESET)" || echo "  LocalStack: ❌"
	@docker exec swe-agent-db mysqladmin ping -u root -p123 >/dev/null 2>&1 && echo "  Database: $(GREEN)✅$(RESET)" || echo "  Database: ❌"
	@docker inspect razorpay-swe-agent-task-execution-worker --format='{{.State.Status}}' 2>/dev/null | grep -q "running" && echo "  Task Worker: $(GREEN)✅$(RESET)" || echo "  Task Worker: ❌"
	@docker inspect razorpay-swe-agent-code-review-worker --format='{{.State.Status}}' 2>/dev/null | grep -q "running" && echo "  Review Worker: $(GREEN)✅$(RESET)" || echo "  Review Worker: ❌"

.PHONY: logs
logs: ## 📋 Show all logs
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml logs -f

.PHONY: logs-tail
logs-tail: ## 📋 Show recent logs
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml logs --tail=50

.PHONY: logs-review-worker
logs-review-worker: ## 📋 Show code review worker logs
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml logs -f swe-agent-code-review-worker

.PHONY: logs-comment-analyzer-worker
logs-comment-analyzer-worker: ## 📋 Show comment analyzer worker logs
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml logs -f swe-agent-comment-analyzer-worker

.PHONY: restart-review-worker
restart-review-worker: ## 🔄 Restart code review worker only
	@echo "$(GREEN)Restarting code review worker...$(RESET)"
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml restart swe-agent-code-review-worker

.PHONY: logs-webhook-receiver
logs-webhook-receiver: ## 📋 Show webhook receiver logs
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml logs -f swe-agent-webhook-receiver

.PHONY: restart-webhook-receiver
restart-webhook-receiver: ## 🔄 Restart webhook receiver only
	@echo "$(GREEN)Restarting webhook receiver...$(RESET)"
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml restart swe-agent-webhook-receiver

.PHONY: restart-comment-analyzer-worker
restart-comment-analyzer-worker: ## 🔄 Restart comment analyzer worker only
	@echo "$(GREEN)Restarting comment analyzer worker...$(RESET)"
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml restart swe-agent-comment-analyzer-worker

##@ Development

.PHONY: setup
setup: ## 🛠️ Setup development environment
	@echo "$(GREEN)Setting up development environment...$(RESET)"
	@python3 -m venv venv || true
	@. venv/bin/activate && pip install --upgrade pip
	@. venv/bin/activate && pip install uv
	@. venv/bin/activate && uv pip install -r requirements.txt

##@ Testing

.PHONY: test
test: ## 🧪 Run all tests
	@echo "$(GREEN)Running all tests...$(RESET)"
	@. venv/bin/activate && pytest tests/ -v

.PHONY: test-unit
test-unit: ## ⚡ Run unit tests (fast)
	@echo "$(GREEN)Running unit tests...$(RESET)"
	@. venv/bin/activate && pytest tests/unit/ -v

.PHONY: test-integration
test-integration: ## 🔗 Run integration tests
	@echo "$(GREEN)Running integration tests...$(RESET)"
	@. venv/bin/activate && pytest tests/integration/ -v

.PHONY: test-coverage
test-coverage: ## 📊 Run tests with coverage report
	@echo "$(GREEN)Running tests with coverage...$(RESET)"
	@. venv/bin/activate && pytest tests/ --cov=src --cov-report=html --cov-report=term-missing -v
	@echo "$(YELLOW)Coverage report generated in htmlcov/index.html$(RESET)"

.PHONY: test-watch
test-watch: ## 👀 Run tests in watch mode (requires pytest-watch)
	@echo "$(GREEN)Running tests in watch mode...$(RESET)"
	@. venv/bin/activate && ptw tests/ -- -v

.PHONY: test-parallel
test-parallel: ## ⚡ Run tests in parallel (requires pytest-xdist)
	@echo "$(GREEN)Running tests in parallel...$(RESET)"
	@. venv/bin/activate && pytest tests/ -n auto -v

.PHONY: test-clean
test-clean: ## 🧹 Clean test artifacts
	@echo "$(GREEN)Cleaning test artifacts...$(RESET)"
	@rm -rf .pytest_cache/
	@rm -rf htmlcov/
	@rm -rf .coverage
	@find . -type d -name "__pycache__" -path "./tests/*" -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)Test artifacts cleaned$(RESET)"

.PHONY: test-ci
test-ci: ## 🤖 Run tests for CI/CD (with coverage and reports)
	@echo "$(GREEN)Running CI tests...$(RESET)"
	@. venv/bin/activate && pytest tests/ \
		--cov=src \
		--cov-report=xml \
		--cov-report=term-missing \
		--junit-xml=test-results.xml \
		--html=test-report.html \
		--self-contained-html \
		-v

.PHONY: worker-local
worker-local: ## 🏃 Run task execution worker locally
	@echo "$(GREEN)Starting task execution worker locally...$(RESET)"
	@. venv/bin/activate && python commands/task_execution_worker.py

.PHONY: review-worker-local
review-worker-local: ## 📝 Run code review worker locally
	@echo "$(GREEN)Starting code review worker locally...$(RESET)"
	@. venv/bin/activate && python commands/code_review_worker.py

.PHONY: ui-local
ui-local: ## 🎨 Run React UI server locally (Vite dev server on port $(UI_PORT))
	@echo "$(GREEN)Starting React UI server locally on port $(UI_PORT)...$(RESET)"
	@$(CHECK_YARN)
	@$(YARN_INSTALL)
	@$(UI_DEV_SERVER)

.PHONY: api-local
api-local: ## 🔧 Run API server locally
	@echo "$(GREEN)Starting API server locally...$(RESET)"
	@. venv/bin/activate && python commands/api.py

.PHONY: mcp-local
mcp-local: ## 🔗 Run MCP server locally
	@echo "$(GREEN)Starting MCP server locally...$(RESET)"
	@. venv/bin/activate && python commands/mcp_server.py

.PHONY: app-local
app-local: ## 🏃 Run API server, worker, and React UI locally (all services)
	@echo "$(GREEN)Starting all local services (API + Worker + UI on port $(UI_PORT))...$(RESET)"
	@$(CHECK_YARN)
	@echo "$(CYAN)[1/3] Starting API server on http://localhost:8002...$(RESET)"
	@. venv/bin/activate && python commands/api.py &
	@API_PID=$$!; \
	echo "$(CYAN)[2/3] Starting task execution worker...$(RESET)"; \
	. venv/bin/activate && python commands/task_execution_worker.py &
	@WORKER_PID=$$!; \
	echo "$(CYAN)[3/3] Starting React UI dev server on http://localhost:$(UI_PORT)...$(RESET)"; \
	$(YARN_INSTALL) 2>/dev/null; \
	$(UI_DEV_SERVER) &
	@UI_PID=$$!; \
	echo ""; \
	echo "$(GREEN)✅ All services started:$(RESET)"; \
	echo "  • API Server:   http://localhost:8002 (PID: $$API_PID)"; \
	echo "  • Task Worker:  Running (PID: $$WORKER_PID)"; \
	echo "  • UI Server:    http://localhost:$(UI_PORT) (PID: $$UI_PID)"; \
	echo ""; \
	echo "$(YELLOW)Press Ctrl+C to stop all services$(RESET)"; \
	echo ""; \
	trap 'echo ""; echo "$(GREEN)Shutting down services...$(RESET)"; kill $$API_PID $$WORKER_PID $$UI_PID 2>/dev/null; wait; echo "$(GREEN)All services stopped$(RESET)"; exit 0' INT TERM; \
	wait $$API_PID $$WORKER_PID $$UI_PID

##@ Maintenance
# Project name ensures containers are consistently named regardless of directory
COMPOSE_PROJECT_NAME ?= swe-agent

.PHONY: destroy
destroy: ## 🗑️  Stop and remove containers but keep volumes (DB data preserved)
	@echo "$(GREEN)Stopping and removing all containers (volumes preserved)...$(RESET)"
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml stop -t 0 2>/dev/null || true
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml rm -f 2>/dev/null || true
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml down --remove-orphans

.PHONY: clean
clean: ## 🧹 Full teardown - stop, remove containers, networks AND volumes
	@echo "$(GREEN)Tearing down services, removing volumes (DB data will be lost)...$(RESET)"
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml stop -t 0 2>/dev/null || true
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml rm -f 2>/dev/null || true
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml down -v --remove-orphans
	@docker system prune -f

.PHONY: reset
reset: clean build start ## 🔄 Complete reset

.PHONY: db-shell
db-shell: ## 💾 MySQL shell access
	@docker exec -it swe-agent-db mysql -u root -p123 swe_agent

.PHONY: queue-clear
queue-clear: ## 🧹 Clear messages from default queue (dev-swe-agent-tasks)
	@python scripts/delete_localstack_messages.py

.PHONY: queue-clear-all
queue-clear-all: ## 🧽 Clear messages from all LocalStack SQS queues
	@python scripts/delete_localstack_messages.py --all

.PHONY: sync-prompts
sync-prompts: ## 📝 Update pr-prompt-kit prompts in code review worker and restart
	@echo "$(GREEN)Syncing pr-prompt-kit prompts to code review worker...$(RESET)"
	@echo "$(YELLOW)Step 1/3: Reinstalling pr-prompt-kit from latest version...$(RESET)"
	@if [ -z "$$GITHUB_TOKEN" ]; then \
		echo "$(YELLOW)WARNING: GITHUB_TOKEN not set. Attempting to read from gh CLI...$(RESET)"; \
		GITHUB_TOKEN=$$(docker exec razorpay-swe-agent-code-review-worker sh -c "gh auth token 2>/dev/null || echo ''"); \
	fi; \
	docker exec razorpay-swe-agent-code-review-worker sh -c "\
		pip uninstall -y ai-pr-reviewer 2>/dev/null || true && \
		if [ -n \"$$GITHUB_TOKEN\" ]; then \
			uv pip install --system git+https://$$GITHUB_TOKEN@github.com/razorpay/ai-pr-reviewer.git@feature/pr-prompt-kit-package; \
		else \
			echo 'ERROR: GITHUB_TOKEN not available. Run: export GITHUB_TOKEN=\$$(gh auth token)' && exit 1; \
		fi \
	"
	@echo "$(YELLOW)Step 2/3: Verifying installation...$(RESET)"
	@docker exec razorpay-swe-agent-code-review-worker python -c "from pr_prompt_kit import __version__; print(f'✓ pr-prompt-kit version: {__version__}')"
	@echo "$(YELLOW)Step 3/3: Restarting code review worker...$(RESET)"
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml restart swe-agent-code-review-worker
	@sleep 2
	@echo "$(GREEN)✓ Prompts synced successfully!$(RESET)"
	@echo "$(CYAN)Verifying worker status...$(RESET)"
	@docker inspect razorpay-swe-agent-code-review-worker --format='{{.State.Status}}' 2>/dev/null | grep -q "running" && echo "  Review Worker: $(GREEN)✅$(RESET)" || echo "  Review Worker: ❌"

.PHONY: sync-prompts-rebuild
sync-prompts-rebuild: ## 🔨 Rebuild code review worker with latest pr-prompt-kit (full rebuild)
	@echo "$(GREEN)Rebuilding code review worker with latest pr-prompt-kit...$(RESET)"
	@echo "$(YELLOW)This will rebuild the Docker image with the latest prompts from the package$(RESET)"
	@if [ -z "$$GITHUB_TOKEN" ]; then \
		echo "$(YELLOW)WARNING: GITHUB_TOKEN not set. Attempting to get from gh CLI...$(RESET)"; \
		export GITHUB_TOKEN=$$(gh auth token 2>/dev/null || echo ''); \
		if [ -z "$$GITHUB_TOKEN" ]; then \
			echo "$(RED)ERROR: GITHUB_TOKEN not available. Please run: export GITHUB_TOKEN=\$$(gh auth token)$(RESET)"; \
			exit 1; \
		fi; \
	fi && \
	GITHUB_TOKEN=$$GITHUB_TOKEN COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml build --no-cache swe-agent-code-review-worker
	@COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker-compose -f docker-compose.dev.yml up -d swe-agent-code-review-worker
	@sleep 3
	@echo "$(GREEN)✓ Code review worker rebuilt successfully!$(RESET)"
	@echo "$(CYAN)Verifying installation...$(RESET)"
	@docker exec razorpay-swe-agent-code-review-worker python -c "from pr_prompt_kit import __version__; print(f'pr-prompt-kit version: {__version__}')"
	@docker inspect razorpay-swe-agent-code-review-worker --format='{{.State.Status}}' 2>/dev/null | grep -q "running" && echo "  Review Worker: $(GREEN)✅$(RESET)" || echo "  Review Worker: ❌"

##@ Info

.PHONY: info
info: ## ℹ️ Show system information
	@echo "$(CYAN)SWE-Agent System Info$(RESET)"
	@echo "$(CYAN)=====================$(RESET)"
	@echo "$(YELLOW)Version:$(RESET) $(VERSION)"
	@echo "$(YELLOW)Environment:$(RESET) $(APP_ENV)"
	@echo "$(YELLOW)UI Server:$(RESET) http://localhost:28001 (Docker) / http://localhost:$(UI_PORT) (Local config)"
	@echo "$(YELLOW)API Server:$(RESET) http://localhost:28002 (Docker) / http://localhost:8002 (Local)"
	@echo "$(YELLOW)MCP Server:$(RESET) http://localhost:28003 (Docker) / http://localhost:28003 (Local)"
	@echo "$(YELLOW)LocalStack:$(RESET) http://localhost:4566"
	@echo "$(YELLOW)Database:$(RESET) localhost:3306"
