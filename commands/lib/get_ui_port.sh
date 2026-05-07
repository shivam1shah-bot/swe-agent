#!/bin/bash
# Helper function to get UI port from frontend env files
# Usage: source this file and call get_ui_port, or run directly

get_ui_port() {
    local env_file="${PROJECT_ROOT:-.}/ui/environments/env.${APP_ENV:-dev_docker}"
    if [ -f "$env_file" ]; then
        local port=$(grep "^APP_UI_PORT" "$env_file" 2>/dev/null | grep -oE '[0-9]+')
        if [ -n "$port" ]; then
            echo "$port"
            return
        fi
    fi
    # Fallback to default env file if environment-specific file doesn't have APP_UI_PORT
    local default_file="${PROJECT_ROOT:-.}/ui/environments/env.default"
    if [ -f "$default_file" ]; then
        local port=$(grep "^APP_UI_PORT" "$default_file" 2>/dev/null | grep -oE '[0-9]+')
        if [ -n "$port" ]; then
            echo "$port"
            return
        fi
    fi
    echo "8001"  # Final fallback
}

# If script is run directly (not sourced), print the port
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    get_ui_port
fi
