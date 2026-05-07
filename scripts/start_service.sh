#!/bin/bash

# Docker-based setup script for SWE Agent local development
#
# This script provides a one-command Docker setup for local development.
# It handles environment configuration, Docker services, and database initialization.
#
# Usage: ./scripts/start_service.sh [setup|start|stop|status|restart|rebuild|rebuild-no-cache|destroy|teardown]

set -e  # Exit on any error

# Colors for output
GREEN='\033[32m'
YELLOW='\033[33m'
CYAN='\033[36m'
RED='\033[31m'
RESET='\033[0m'

# Project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Docker Compose project name for consistent container naming
export COMPOSE_PROJECT_NAME=swe-agent

log_info() {
    echo -e "${CYAN}i️  $1${RESET}"
}

log_success() {
    echo -e "${GREEN}✅ $1${RESET}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${RESET}"
}

log_error() {
    echo -e "${RED}❌ $1${RESET}"
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if Docker is installed and running
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    if ! docker info &> /dev/null; then
        log_error "Docker is not running. Please start Docker first."
        exit 1
    fi

    # Check if docker-compose is available
    if ! command -v docker-compose &> /dev/null; then
        log_error "docker-compose is not installed. Please install docker-compose first."
        exit 1
    fi

    # Check if make is available
    if ! command -v make &> /dev/null; then
        log_error "make is not installed. Please install make first."
        exit 1
    fi

    log_success "All prerequisites met"
}

setup_environment() {
    log_info "Setting up environment configuration..."

    # Check if dev_docker.toml exists, if not create it from default
    if [ ! -f "$PROJECT_ROOT/environments/env.dev_docker.toml" ]; then
        log_info "Creating dev_docker.toml from env.default.toml..."
        cp "$PROJECT_ROOT/environments/env.default.toml" "$PROJECT_ROOT/environments/env.dev_docker.toml"
        log_success "Created environments/env.dev_docker.toml"
    else
        log_info "Using existing environments/env.dev_docker.toml"
    fi
}

start_services() {
    log_info "Starting SWE Agent Docker services..."

    cd "$PROJECT_ROOT"

    # Use make to start all services
    make start || {
        log_error "Failed to start services - you may have conflicting containers from a previous run"
        log_info "Try './scripts/start_service.sh destroy && ./scripts/start_service.sh start' for a clean start"
        exit 1
    }

    log_success "Docker services started"

    # Wait a bit for services to fully initialize
    log_info "Waiting for services to initialize..."
    sleep 10
}

setup_database() {
    log_info "Setting up database with migrations and seeds..."

    cd "$PROJECT_ROOT"

    # Run the database setup script
    if [ -f "$PROJECT_ROOT/scripts/setup_database.sh" ]; then
        bash "$PROJECT_ROOT/scripts/setup_database.sh"
        log_success "Database setup completed"
    else
        log_error "Database setup script not found at scripts/setup_database.sh"
        exit 1
    fi
}

stop_services() {
    log_info "Stopping SWE Agent Docker services..."

    cd "$PROJECT_ROOT"
    make stop

    log_success "Docker services stopped"
}

show_status() {
    log_info "Showing service status..."

    cd "$PROJECT_ROOT"
    make status
}

restart_services() {
    log_info "Restarting SWE Agent services..."
    stop_services
    sleep 2
    start_services
    setup_database
}

rebuild_services() {
    log_info "Rebuilding SWE Agent services (with cache)..."

    cd "$PROJECT_ROOT"
    make rebuild

    log_success "Services rebuilt and restarted"
}

rebuild_services_no_cache() {
    log_info "Rebuilding SWE Agent services (no-cache - slower, use after Dockerfile changes)..."

    cd "$PROJECT_ROOT"
    make rebuild-no-cache

    log_success "Services rebuilt and restarted"
}

destroy_services() {
    log_info "Removing SWE Agent containers and networks (volumes preserved)..."
    
    cd "$PROJECT_ROOT"
    make destroy
    
    log_success "Containers removed - database and redis data preserved"
}

teardown_services() {
    log_info "Tearing down SWE Agent services and removing volumes..."
    
    cd "$PROJECT_ROOT"
    make clean
    
    log_success "All services and volumes cleaned up (DB data deleted)"
}

full_setup() {
    log_info "🚀 Starting complete SWE Agent Docker setup..."
    echo ""

    check_prerequisites
    setup_environment
    start_services
    setup_database

    echo ""
    log_success "🎉 SWE Agent setup completed successfully!"
    echo ""
    echo -e "${CYAN}📋 Service URLs:${RESET}"
    echo "   • Frontend (UI): http://localhost:28001"
    echo "   • Backend (API): http://localhost:28002"
    echo "   • API Documentation: http://localhost:28002/docs"
    echo "   • Database: localhost:23306"
    echo "   • Redis: localhost:26389"
    echo "   • LocalStack (SQS): http://localhost:4566"
    echo ""
    echo -e "${CYAN}🛠️  Useful Commands:${RESET}"
    echo "   • Check status:      ./scripts/start_service.sh status"
    echo "   • View logs:         make logs"
    echo "   • Stop services:     ./scripts/start_service.sh stop"
    echo "   • Restart:           ./scripts/start_service.sh restart"
    echo "   • Rebuild (cached):  ./scripts/start_service.sh rebuild"
    echo "   • Rebuild (clean):   ./scripts/start_service.sh rebuild-no-cache"
    echo "   • Destroy:           ./scripts/start_service.sh destroy  (remove containers, keep data)"
    echo "   • Teardown:          ./scripts/start_service.sh teardown (remove containers + data)"
    echo ""
}

case ${1:-setup} in
    start)
        check_prerequisites
        setup_environment
        start_services
        ;;
    stop)
        stop_services
        ;;
    status)
        show_status
        ;;
    restart)
        restart_services
        ;;
    rebuild)
        check_prerequisites
        rebuild_services
        ;;
    rebuild-no-cache)
        check_prerequisites
        rebuild_services_no_cache
        ;;
    destroy)
        destroy_services
        ;;
    teardown)
        teardown_services
        ;;
    setup)
        full_setup
        ;;
    *)
        echo "SWE Agent Docker Setup Script"
        echo "=============================="
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  setup           - Complete setup (default): environment + start services + database setup"
        echo "  start           - Start Docker services only"
        echo "  stop            - Stop all Docker services (containers preserved)"
        echo "  status          - Show service status and health"
        echo "  restart         - Restart all services and re-setup database"
        echo "  rebuild         - Rebuild images (with cache) and restart services"
        echo "  rebuild-no-cache - Rebuild images (no cache) and restart - use after Dockerfile changes"
        echo "  destroy         - Remove containers/networks but keep volumes (DB data preserved)"
        echo "  teardown        - Remove everything including volumes (DB data lost)"
        echo ""
        echo "Examples:"
        echo "  $0                  # Run complete setup"
        echo "  $0 setup            # Same as above"
        echo "  $0 start            # Just start services"
        echo "  $0 stop             # Pause services"
        echo "  $0 status           # Check if everything is running"
        echo "  $0 rebuild          # Quick rebuild (cached) - for code changes"
        echo "  $0 rebuild-no-cache # Full rebuild (no cache) - for Dockerfile changes"
        echo "  $0 destroy          # Fresh start, keep database"
        echo "  $0 teardown         # Clean slate - delete everything"
        echo ""
        echo "This script uses Docker Compose and Make for orchestration."
        echo "Make sure Docker is running before executing this script."
        ;;
esac
