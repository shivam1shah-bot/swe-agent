# Environment Configuration

SWE Agent uses TOML-based configuration with environment-specific overrides.

## Environment Selection

Set via `APP_ENV` environment variable (defaults to `dev`):

```bash
APP_ENV=stage ./commands/run.sh api
```

## Available Environments

- **dev**: Local development with LocalStack
- **dev_docker**: Docker-based local development
- **stage**: Pre-production with real AWS services
- **prod**: Production environment

## Configuration Hierarchy

Configuration is merged in order (later overrides earlier):

1. `environments/env.default.toml` - Base settings
2. `environments/env.{APP_ENV}.toml` - Environment-specific
3. `environments/env.{APP_ENV}.local.toml` - Local overrides (git-ignored)
4. Environment variables - Runtime secrets

## Local Overrides

Create `env.{ENV}.local.toml` for machine-specific settings:

```toml
# environments/env.dev.local.toml
[database]
port = 3307
```

These files are git-ignored and override without modifying tracked files.

## Secret Injection

Use environment variables for secrets (not TOML files):

```bash
export DATABASE_URL="mysql+mysqlconnector://user:pass@host:port/db"
```

This prevents secrets from being committed.

## Database Setup

Initialize local database:

```bash
./scripts/setup_database.sh
```

For staging/production, database setup is handled by infrastructure/deployment automation.
