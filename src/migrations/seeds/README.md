# Database Seed Data

This directory contains seed data for local development environment setup.

## Overview

Seed data is used to populate the database with initial data needed for local development and testing. Unlike migrations, seed data is:

- **Environment-specific**: Only run in local/development environments
- **Idempotent**: Can be run multiple times safely
- **Optional**: Not required for production deployments

## Structure

```
src/migrations/seeds/
├── README.md                 # This file
├── run_seeds.py             # Main seed runner script
└── agents_catalogue_items.py     # Agents catalogue seed data
```

## Usage

### Automatic (during database setup)

Seeds are automatically run when setting up the database locally:

```bash
./scripts/setup_database.sh
```

### Manual execution

You can also run seeds manually:

```bash
# Run all seeds
python src/migrations/seeds/run_seeds.py

# Run specific seed module
python src/migrations/seeds/agents_catalogue_items.py
```

## Adding New Seed Data

1. Create a new seed file (e.g., `users.py`)
2. Follow the pattern from `agents_catalogue_items.py`:
   - Define a main seed function
   - Handle existing data gracefully (use `INSERT ... ON DUPLICATE KEY UPDATE`)
   - Include proper logging
3. Add the seed function to `run_seeds.py`

## Current Seed Data

### Agents Catalogue Items (`agents_catalogue_items.py`)

- **Spinnaker V3 Pipeline Generator**: Micro-frontend for creating Spinnaker pipelines

## Notes

- Seeds use the same database connection as the main application
- All seed operations are logged for debugging
- Seeds are designed to be safe to run multiple times
- Seed data is not tracked in migration history
