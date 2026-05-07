#!/bin/bash

# SWE Agent CMD Runner
# This script runs commands from the cmd folder for production deployment

# Get the project root (parent directory)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Set environment variables
export PYTHONPATH="$PROJECT_ROOT:$PROJECT_ROOT/src"
export APP_ENV=${APP_ENV:-prod}

# Helper function to get UI port from frontend env files (falls back to 8001)
get_ui_port() {
    local env_file="$PROJECT_ROOT/ui/environments/env.${APP_ENV}"
    if [ -f "$env_file" ]; then
        local port=$(grep "^APP_UI_PORT" "$env_file" 2>/dev/null | grep -oE '[0-9]+')
        if [ -n "$port" ]; then
            echo "$port"
            return
        fi
    fi
    # Fallback to default env file if environment-specific file doesn't have APP_UI_PORT
    local default_file="$PROJECT_ROOT/ui/environments/env.default"
    if [ -f "$default_file" ]; then
        local port=$(grep "^APP_UI_PORT" "$default_file" 2>/dev/null | grep -oE '[0-9]+')
        if [ -n "$port" ]; then
            echo "$port"
            return
        fi
    fi
    echo "8001"  # Final fallback
}

UI_PORT=$(get_ui_port)

echo "SWE Agent CMD Runner"
echo "Project Root: $PROJECT_ROOT"
echo "Environment: $APP_ENV"
echo "UI Port: $UI_PORT"

# Change to project root for execution
cd "$PROJECT_ROOT"

# Parse command
COMMAND=${1:-help}

case $COMMAND in
    "api")
        echo "Starting SWE Agent API server (port 8002)..."
        shift  # Remove 'api' from arguments
        python commands/api.py "$@"
        ;;
    "ui")
        echo "Starting React UI server on port $UI_PORT..."
        shift  # Remove 'ui' from arguments
        cd ui || exit 1

        # Check if node_modules exists, if not install dependencies
        if [ ! -d "node_modules" ]; then
            echo "Installing dependencies..."
            if command -v yarn &> /dev/null; then
                yarn install --immutable
            else
                echo "Error: yarn is not available. Please enable Corepack first."
                echo "  corepack enable"
                exit 1
            fi
        fi

        # Check if dist exists (production build), if not build it
        if [ ! -d "dist" ]; then
            echo "Building UI for production..."
            yarn build
        fi

        echo "Starting UI server on http://localhost:$UI_PORT"
        echo "  • Production mode: PORT=$UI_PORT node server.js"
        echo "  • For dev mode with hot reload: cd ui && PORT=$UI_PORT yarn dev"
        echo ""
        PORT=$UI_PORT node server.js "$@"
        ;;
    "worker")
        echo "Starting Task Execution Worker..."
        python commands/task_execution_worker.py
        ;;
    "both")
        echo "Starting both API server and worker..."
        echo "Starting API server in background..."
        python commands/api.py --workers 4 &
        API_PID=$!
        echo "API server started with PID: $API_PID"

        echo "Starting worker..."
        python commands/task_execution_worker.py &
        WORKER_PID=$!
        echo "Worker started with PID: $WORKER_PID"

        # Wait for both processes
        wait $API_PID $WORKER_PID
        ;;
    "all")
        echo "Starting all services (API + Worker + UI on port $UI_PORT)..."
        echo ""

        # Check if yarn is available for UI
        if ! command -v yarn &> /dev/null; then
            echo "Error: yarn is required to start the UI."
            echo "Please enable Corepack to use Yarn 4:"
            echo "  corepack enable"
            exit 1
        fi

        # Start API server in background
        echo "[1/3] Starting API server on http://localhost:8002..."
        python commands/api.py --workers 4 &
        API_PID=$!

        # Start worker in background
        echo "[2/3] Starting task execution worker..."
        python commands/task_execution_worker.py &
        WORKER_PID=$!

        # Start UI server in background
        echo "[3/3] Starting UI server on http://localhost:$UI_PORT..."
        cd ui || exit 1

        # Install dependencies if needed
        if [ ! -d "node_modules" ]; then
            echo "Installing UI dependencies..."
            yarn install --immutable
        fi

        # Build if needed
        if [ ! -d "dist" ]; then
            echo "Building UI..."
            yarn build
        fi

        # Start UI in background with the configured port
        PORT=$UI_PORT node server.js &
        UI_PID=$!
        cd ..

        echo ""
        echo "✅ All services started:"
        echo "  • API Server:   http://localhost:8002 (PID: $API_PID)"
        echo "  • UI Server:    http://localhost:$UI_PORT (PID: $UI_PID)"
        echo "  • Task Worker:  Running (PID: $WORKER_PID)"
        echo ""
        echo "Press Ctrl+C to stop all services"
        echo ""

        # Handle shutdown
        cleanup() {
            echo ""
            echo "Shutting down services..."
            kill $API_PID $WORKER_PID $UI_PID 2>/dev/null
            wait
            echo "All services stopped"
            exit 0
        }
        trap cleanup SIGINT SIGTERM

        # Wait for all processes
        wait $API_PID $WORKER_PID $UI_PID
        ;;
    "sender-test")
        echo "Running sender test..."
        python -c "from src.providers.worker import send_to_worker; print('Testing sender...'); result = send_to_worker({'event_type': 'test', 'message': 'Hello from commands/run.sh!'}); print(f'Result: {result}')"
        ;;
    "help"|*)
        echo ""
        echo "Usage: ./commands/run.sh [command]"
        echo ""
        echo "Available commands:"
        echo "  api          - Start the SWE Agent FastAPI server (port 8002)"
        echo "  ui           - Start the React UI server (port $UI_PORT from config)"
        echo "  worker       - Start the SQS task execution worker"
        echo "  both         - Start both API server and worker"
        echo "  all          - Start API server, worker, and UI together"
        echo "  sender-test  - Test the SQS sender functionality"
        echo "  help         - Show this help message"
        echo ""
        echo "Environment variables:"
        echo "  APP_ENV      - Environment (dev/dev_docker/stage/prod) [default: prod]"
        echo "  PORT         - Override UI port (default: $UI_PORT from config)"
        echo ""
        echo "Note: Use command line arguments for additional configuration options."
        echo ""
        ;;
esac
