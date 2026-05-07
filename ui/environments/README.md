# UI Environment Configuration

This directory contains environment-specific configuration files for the SWE Agent UI.

## Configuration System

The UI uses a layered configuration system with **env files** (standard key-value format):

### Environment Files

```
environments/
├── env.default      # Base configuration (required)
├── env.dev         # Development environment
├── env.dev_docker  # Docker development environment
├── env.stage       # Staging environment
└── env.prod        # Production environment
```

### Configuration Structure

Each env file uses flat key-value pairs with underscore prefixes for sections:

```bash
# App Configuration
APP_NAME="SWE Agent"
APP_ENVIRONMENT="dev"
APP_API_BASE_URL="http://localhost:8002"
APP_DEBUG=true

# Performance Configuration
PERFORMANCE_API_TIMEOUT=10000
PERFORMANCE_POLLING_INTERVAL=5000
PERFORMANCE_PAGINATION_SIZE=10

# Features Configuration
FEATURES_ENABLE_DARK_MODE=true
FEATURES_ENABLE_AUTO_REFRESH=true
FEATURES_ENABLE_NOTIFICATIONS=true

# Logging Configuration
LOGGING_LEVEL="debug"
LOGGING_LOG_API_REQUESTS=true
```

### Layered Configuration Loading

1. **Base Configuration**: `env.default` provides default values
2. **Environment Override**: `env.{environment}` overrides specific settings
3. **Deep Merge**: Settings are merged, with environment values taking precedence

### Runtime Loading

The configuration is loaded at runtime via two paths:

#### 1. Build-time (Vite Development)

- Uses hardcoded values in `vite.config.ts` for development server
- Values must match corresponding env files for consistency

#### 2. Production Runtime (Express Server)

- Loads full configuration from env files via `config-loader.server.js`
- Serves configuration through `/api/config` endpoint
- Frontend fetches config at startup

### Environment Detection

Environment is determined by (in order of precedence):

1. `APP_ENV` environment variable
2. `NODE_ENV` environment variable
3. Default: `'dev'`

### Fail-Fast Behavior

The system **fails immediately** if required configuration files are missing:

- `env.default` is always required
- Environment-specific files must exist for each environment used
- **No hardcoded fallbacks** - system exits on missing configs

### Examples

#### Development Environment

```bash
# Uses env.dev
NODE_ENV=dev npm run dev
```

#### Docker Environment

```bash
# Uses env.dev_docker
APP_ENV=dev_docker npm start
```

#### Production Environment

```bash
# Uses env.prod
APP_ENV=prod npm start
```

### Adding New Environments

1. Create `env.{environment}` file with required settings
2. Update `getAllConfigs()` in `config-loader.server.js` to include new environment
3. Add corresponding API URL to `vite.config.ts` if needed

### Configuration Structure

The env configuration is parsed into a structured object:

```typescript
interface UIConfig {
  app: {
    name: string;
    environment: string;
    api_base_url: string;
    ui_base_url: string;
    ui_port: number; // Port for UI dev server (e.g., 8001)
    debug: boolean;
  };
  performance: {
    api_timeout: number;
    polling_interval: number;
    pagination_size: number;
  };
  features: {
    enable_dark_mode: boolean;
    enable_auto_refresh: boolean;
    enable_notifications: boolean;
  };
  logging: {
    level: string;
    log_api_requests: boolean;
  };
}
```

### Type Conversion

The env loader automatically converts string values:

- `"true"/"false"` → boolean
- `"123"` → number
- `"123.45"` → float
- `"quoted strings"` → unquoted strings
- Other values remain as strings

### Files in this Directory

- **env.default** - Base configuration with default values
- **env.dev** - Development environment settings
- **env.dev_docker** - Docker development settings (different API URLs)
- **env.stage** - Staging environment settings
- **env.prod** - Production environment settings
- **config-loader.server.js** - Server-side configuration loader
- **config-loader.server.d.ts** - TypeScript declarations
- **config.ts** - Client-side configuration types (legacy)
- **index.ts** - Environment configuration exports (legacy)

### Migration from TOML

This system was migrated from TOML files to use standard env file format for simplicity:

- No additional dependencies required (removed `@iarna/toml`)
- Standard environment file format
- Same layered configuration behavior
- Maintained fail-fast error handling
