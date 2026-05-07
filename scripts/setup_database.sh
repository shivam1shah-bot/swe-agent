#!/bin/bash
# Enhanced database setup script for SWE Agent
# Works with both local MySQL and Docker Compose setups

set -e  # Exit on any error

echo "🔧 Setting up SWE Agent database..."

# Function to detect Docker Compose setup
detect_docker_compose() {
    if docker-compose -f docker-compose.dev.yml ps | grep -q "swe-agent-db"; then
        echo "docker-compose"
    elif docker ps --filter "name=swe-agent-db" --format "{{.Names}}" | grep -q "swe-agent-db"; then
        echo "docker"
    elif docker ps --filter "name=mysql" --format "{{.Names}}" | grep -q "^mysql$"; then
        echo "docker-mysql"
    elif command -v mysql &> /dev/null; then
        echo "local"
    else
        echo "none"
    fi
}

# Function to run migrations in Docker
run_docker_migrations() {
    local container_name="$1"
    
    echo "🚀 Running database migrations in Docker container..."
    
    # Run migrations inside the API container
    docker exec "$container_name" python scripts/dev_startup.py --migrations-only 2>/dev/null || {
        echo "💡 Using direct migration approach..."
        docker exec "$container_name" python -c "
import sys
sys.path.insert(0, '/app/src')
from src.providers.config_loader import get_config
from src.providers.database.connection import initialize_engine
from src.migrations.manager import MigrationManager

try:
    config = get_config()
    engine = initialize_engine(config)
    migration_manager = MigrationManager(engine)
    success = migration_manager.run_migrations()
    print('✅ Migrations completed successfully' if success else '❌ Migrations failed')
    if not success:
        sys.exit(1)
except Exception as e:
    print(f'❌ Migration error: {e}')
    sys.exit(1)
"
    }
    
    if [ $? -ne 0 ]; then
        echo "❌ Migrations failed! Cannot proceed with seeds."
        exit 1
    fi
}

# Function to run seeds in Docker
run_docker_seeds() {
    local container_name="$1"
    
    echo "🌱 Running database seeds in Docker container..."
    
    # First check if seeds are already populated
    echo "📋 Checking existing catalogue items..."
    local existing_count=$(docker exec "$container_name" python -c "
import sys
import os
sys.path.insert(0, '/app/src')
os.environ['PYTHONWARNINGS'] = 'ignore'

from src.providers.config_loader import get_config
from src.providers.database.connection import initialize_engine
from sqlalchemy import text
import logging
logging.getLogger().setLevel(logging.ERROR)

try:
    config = get_config()
    engine = initialize_engine(config)
    with engine.connect() as conn:
        result = conn.execute(text('SELECT COUNT(*) FROM agents_catalogue_items'))
        count = result.scalar()
        print(f'COUNT:{count}')
except Exception as e:
    print('COUNT:0')  # Assume empty if error
" 2>/dev/null | grep "COUNT:" | cut -d: -f2)
    
    # Ensure existing_count is a valid integer
    if ! [[ "$existing_count" =~ ^[0-9]+$ ]]; then
        existing_count=0
    fi
    
    if [ "$existing_count" -gt 0 ]; then
        echo "📋 Found $existing_count existing catalogue items. Updating with latest seed data..."
    else
        echo "📋 No existing catalogue items found. Populating with seed data..."
    fi
    
    # Run seeds inside the API container
    docker exec "$container_name" python -c "
import sys
sys.path.insert(0, '/app/src')
from src.providers.config_loader import get_config
from src.providers.database.connection import initialize_engine
from src.migrations.seeds.agents_catalogue_items import seed_agents_catalogue_items

try:
    config = get_config()
    engine = initialize_engine(config)
    seed_agents_catalogue_items(engine)
    print('✅ Seeds completed successfully')
except Exception as e:
    print(f'❌ Seed error: {e}')
    sys.exit(1)
"
    
    if [ $? -eq 0 ]; then
        # Verify seeds were applied
        local final_count=$(docker exec "$container_name" python -c "
import sys
import os
sys.path.insert(0, '/app/src')
os.environ['PYTHONWARNINGS'] = 'ignore'

from src.providers.config_loader import get_config
from src.providers.database.connection import initialize_engine
from sqlalchemy import text
import logging
logging.getLogger().setLevel(logging.ERROR)

try:
    config = get_config()
    engine = initialize_engine(config)
    with engine.connect() as conn:
        result = conn.execute(text('SELECT COUNT(*) FROM agents_catalogue_items'))
        count = result.scalar()
        print(f'COUNT:{count}')
except Exception as e:
    print('COUNT:0')
" 2>/dev/null | grep "COUNT:" | cut -d: -f2)
        
        # Ensure final_count is a valid integer
        if ! [[ "$final_count" =~ ^[0-9]+$ ]]; then
            final_count=0
        fi
        
        echo "📊 Catalogue now contains $final_count items"
        
        # Show what was seeded
        echo "📋 Seeded catalogue items:"
        docker exec "$container_name" python -c "
import sys
sys.path.insert(0, '/app/src')
from src.providers.config_loader import get_config
from src.providers.database.connection import initialize_engine
from sqlalchemy import text
import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

try:
    config = get_config()
    engine = initialize_engine(config)
    with engine.connect() as conn:
        result = conn.execute(text('SELECT id, name, lifecycle FROM agents_catalogue_items ORDER BY created_at'))
        rows = result.fetchall()
        for row in rows:
            print(f'  • {row[1]} ({row[2]})')
except Exception as e:
    print(f'  ❌ Error listing items: {e}')
" 2>/dev/null
    else
        echo "⚠️  Seed data setup failed, but migrations completed."
        echo "You can manually run seed data later."
    fi
}

# Detect the environment
ENV_TYPE=$(detect_docker_compose)

case $ENV_TYPE in
    "docker-compose")
        echo "💡 Found Docker Compose setup. Using container-based approach."
        
        # Check if containers are running
        if ! docker-compose -f docker-compose.dev.yml ps | grep -q "Up"; then
            echo "⚠️  Docker Compose containers are not running."
            echo "Please start the containers first:"
            echo "  docker-compose -f docker-compose.dev.yml up -d"
            exit 1
        fi
        
        # Wait for database to be ready
        echo "⏳ Waiting for database to be ready..."
        timeout=60
        counter=0
        while [ $counter -lt $timeout ]; do
            if docker exec swe-agent-db mysqladmin ping -h localhost -u root -proot --silent; then
                echo "✅ Database is ready!"
                break
            fi
            echo "Waiting for database... ($counter/$timeout)"
            sleep 2
            counter=$((counter + 2))
        done
        
        if [ $counter -ge $timeout ]; then
            echo "❌ Database did not become ready within $timeout seconds"
            exit 1
        fi
        
        # Find API container name
        API_CONTAINER=$(docker-compose -f docker-compose.dev.yml ps -q swe-agent-api 2>/dev/null || echo "")
        if [ -z "$API_CONTAINER" ]; then
            # Try alternative container name
            API_CONTAINER=$(docker ps --filter "name=razorpay-swe-agent-api" --format "{{.Names}}" | head -1)
        fi
        
        if [ -z "$API_CONTAINER" ]; then
            echo "❌ Could not find API container. Please ensure Docker Compose is running."
            exit 1
        fi
        
        echo "🐳 Using API container: $API_CONTAINER"
        
        # Database setup is handled by Docker Compose, run migrations then seeds
        run_docker_migrations "$API_CONTAINER"
        run_docker_seeds "$API_CONTAINER"
        
        echo ""
        echo "✅ Docker Compose database setup complete!"
        echo ""
        echo "Services are available at:"
        echo "  Frontend: http://localhost:28001"
        echo "  API: http://localhost:28002"
        echo "  Database: localhost:23306"
        ;;
        
    "docker")
        echo "💡 Found standalone Docker container. Using 'docker exec' to connect."
        MYSQL_CMD="docker exec -i swe-agent-db mysql"
        # Continue with standard setup...
        ;;
        
    "docker-mysql")
        echo "💡 Found MySQL running in Docker. Using 'docker exec' to connect."
        MYSQL_CMD="docker exec -i mysql mysql"
        # Continue with standard setup...
        ;;
        
    "local")
        echo "💡 Found local MySQL installation."
        MYSQL_CMD="mysql"
        # Continue with standard setup...
        ;;
        
    "none")
        echo "❌ No MySQL installation found!"
        echo ""
        echo "Available options:"
        echo "  1. Install MySQL locally: brew install mysql (macOS)"
        echo "  2. Use Docker Compose: docker-compose -f docker-compose.dev.yml up -d"
        echo "  3. Run standalone MySQL: docker run --name mysql -e MYSQL_ROOT_PASSWORD=root -p 3306:3306 -d mysql:8.0"
        exit 1
        ;;
esac

# For non-Docker Compose setups, continue with the original logic
if [ "$ENV_TYPE" != "docker-compose" ]; then
    # Get MySQL credentials
    read -p "Enter MySQL root username [root]: " mysql_user
    mysql_user=${mysql_user:-root}

    echo "Enter MySQL root password (leave empty if no password):"
    read -s mysql_pass

    # Create the SQL commands
    SQL_COMMANDS="
-- MySQL setup script for SWE Agent
-- Creates the database and user with appropriate permissions

-- Create database if it doesn't exist
CREATE DATABASE IF NOT EXISTS swe_agent CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Create user if it doesn't exist and grant privileges
-- NOTE: In production, use a more secure password and restrict host access
CREATE USER IF NOT EXISTS 'swe_agent'@'localhost' IDENTIFIED BY 'swe_agent_password';
CREATE USER IF NOT EXISTS 'swe_agent'@'%' IDENTIFIED BY 'swe_agent_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON swe_agent.* TO 'swe_agent'@'localhost';
GRANT ALL PRIVILEGES ON swe_agent.* TO 'swe_agent'@'%';

-- Flush privileges to ensure they take effect
FLUSH PRIVILEGES;

-- Display success message
SELECT 'SWE Agent database and user created successfully!' AS message;

-- Use the database
USE swe_agent;
"

    # Run the SQL commands
    echo "Creating database and user..."
    if [ -z "$mysql_pass" ]; then
        echo "$SQL_COMMANDS" | $MYSQL_CMD -u "$mysql_user"
    else
        echo "$SQL_COMMANDS" | $MYSQL_CMD -u "$mysql_user" -p"$mysql_pass"
    fi

    if [ $? -eq 0 ]; then
        echo "✅ Database setup complete!"
        
        # Check if Python is available to run migrations and seeds
        if command -v python3 &> /dev/null; then
            python_cmd="python3"
        elif command -v python &> /dev/null; then
            python_cmd="python"
        else
            python_cmd=""
        fi
        
        if [ -n "$python_cmd" ]; then
            # Change to project root to ensure src path is found
            cd "$(dirname "$0")/.."

            # Run migrations to create tables
            echo "🚀 Running database migrations..."
            $python_cmd -c "
import sys
sys.path.insert(0, 'src')
from src.providers.config_loader import get_config
from src.providers.database.connection import initialize_engine
from src.migrations.manager import MigrationManager

try:
    config = get_config()
    engine = initialize_engine(config)
    migration_manager = MigrationManager(engine)
    success = migration_manager.run_migrations()
    if not success:
        sys.exit(1)
except Exception as e:
    print(f'Migration error: {e}')
    sys.exit(1)
"
            if [ $? -ne 0 ]; then
                echo "❌ Migrations failed! Please check the output above."
                exit 1
            fi
            echo "✅ Migrations applied successfully."

            # Run seed data for local development
            echo ""
            echo "🌱 Setting up seed data for local development..."
            
            # First check if seeds are already populated
            echo "📋 Checking existing catalogue items..."
            existing_count=$($python_cmd -c "
import sys
sys.path.insert(0, 'src')
from src.providers.config_loader import get_config
from src.providers.database.connection import initialize_engine
from sqlalchemy import text
import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

try:
    config = get_config()
    engine = initialize_engine(config)
    with engine.connect() as conn:
        result = conn.execute(text('SELECT COUNT(*) FROM agents_catalogue_items'))
        count = result.scalar()
        print(count)
except Exception as e:
    print('0')  # Assume empty if error
" 2>/dev/null | tail -1)
            
            # Ensure existing_count is a valid integer
            if ! [[ "$existing_count" =~ ^[0-9]+$ ]]; then
                existing_count=0
            fi
            
            if [ "$existing_count" -gt 0 ]; then
                echo "📋 Found $existing_count existing catalogue items. Updating with latest seed data..."
            else
                echo "📋 No existing catalogue items found. Populating with seed data..."
            fi
            
            if [ -f "src/migrations/seeds/run_seeds.py" ]; then
                $python_cmd src/migrations/seeds/run_seeds.py
                if [ $? -eq 0 ]; then
                    # Verify seeds were applied
                    final_count=$($python_cmd -c "
import sys
sys.path.insert(0, 'src')
from src.providers.config_loader import get_config
from src.providers.database.connection import initialize_engine
from sqlalchemy import text
import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

try:
    config = get_config()
    engine = initialize_engine(config)
    with engine.connect() as conn:
        result = conn.execute(text('SELECT COUNT(*) FROM agents_catalogue_items'))
        count = result.scalar()
        print(count)
except Exception as e:
    print('0')
" 2>/dev/null | tail -1)
                    
                    # Ensure final_count is a valid integer
                    if ! [[ "$final_count" =~ ^[0-9]+$ ]]; then
                        final_count=0
                    fi
                    
                    echo "✅ Seed data setup complete!"
                    echo "📊 Catalogue now contains $final_count items"
                    
                    # Show what was seeded
                    echo "📋 Seeded catalogue items:"
                    $python_cmd -c "
import sys
sys.path.insert(0, 'src')
from src.providers.config_loader import get_config
from src.providers.database.connection import initialize_engine
from sqlalchemy import text
import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

try:
    config = get_config()
    engine = initialize_engine(config)
    with engine.connect() as conn:
        result = conn.execute(text('SELECT id, name, lifecycle FROM agents_catalogue_items ORDER BY created_at'))
        rows = result.fetchall()
        for row in rows:
            print(f'  • {row[1]} ({row[2]})')
except Exception as e:
    print(f'  ❌ Error listing items: {e}')
" 2>/dev/null
                else
                    echo "⚠️  Seed data setup failed, but database is ready."
                    echo "You can manually run seed data later with: $python_cmd src/migrations/seeds/run_seeds.py"
                fi
            else
                echo "⚠️  Seed script not found. Skipping seed data setup."
            fi
        else
            echo "⚠️  Python not found. Skipping migrations and seed data setup."
            echo "Migrations will run automatically when you start the server."
        fi
        
        echo ""
        echo "Database details:"
        echo "  Database: swe_agent"
        echo "  Username: swe_agent"
        echo "  Password: swe_agent_password"
        echo ""
        echo "You can now start the SWE Agent application:"
        echo "  ./commands/run.sh all    # Start all services"
        echo "  ./commands/run.sh help   # See all options"
        echo ""
        echo "The database migrations will run automatically on startup."
    else
        echo "❌ Database setup failed!"
        exit 1
    fi
fi 