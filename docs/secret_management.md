# Secret Management

## Environment Variable Overrides

Use **double underscores (`__`)** to override TOML configuration values:

```bash
# Format: SECTION__SUBSECTION__KEY=value
export DATABASE__PASSWORD="secure_password"
export GITHUB__TOKEN="ghp_your_token"
export AWS__ACCESS_KEY_ID="AKIA..."
```

## Local Configuration Files

Create local override files (gitignored):

- `environments/env.{env}.local.toml` - Environment-specific secrets
- `environments/env.default.local.toml` - Base overrides

Example `env.stage.local.toml`:

```toml
[database]
password = "actual_stage_password"

[github]
token = "ghp_your_github_token"
```

## Configuration Loading Order

1. `env.default.toml` (base)
2. `env.{APP_ENV}.toml` (environment-specific)
3. `env.default.local.toml` (local base overrides)
4. `env.{APP_ENV}.local.toml` (local env overrides)
5. **Environment Variables** (highest priority)

## Best Practices

- Use local `.toml` files for development secrets
- Use environment variables for production deployments
- Never commit secrets to version control
- Use secret management systems (AWS Secrets Manager, etc.) in production
