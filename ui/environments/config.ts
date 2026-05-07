// UI Environment Configuration Types

export interface UIAppConfig {
  name: string;
  environment: string;
  api_base_url: string;
  /** @deprecated Discover now uses the main API via Python proxy (api/v1/discover/*) */
  discover_api_base_url: string;
  ui_base_url: string;
  ui_port: number;
  debug: boolean;
}

export interface UIPerformanceConfig {
  api_timeout: number;          // API request timeout in milliseconds
  polling_interval: number;     // Auto-refresh interval in milliseconds  
  pagination_size: number;      // Default items per page
}

export interface UIFeaturesConfig {
  enable_dark_mode: boolean;
  enable_auto_refresh: boolean;
  enable_notifications: boolean;
}

export interface UILoggingConfig {
  level: 'debug' | 'info' | 'warn' | 'error';
  log_api_requests: boolean;
}

export interface UIAuthConfig {
  username: string;
  password: string;
}

export interface UIEnvironmentConfig {
  app: UIAppConfig;
  performance: UIPerformanceConfig;
  features: UIFeaturesConfig;
  logging: UILoggingConfig;
  auth: UIAuthConfig;
}

// Base configuration with sensible defaults
export const baseConfig: UIEnvironmentConfig = {
  app: {
    name: "Vyom",
    environment: "default",
    api_base_url: "http://localhost:8002",
    discover_api_base_url: "http://localhost:8004",
    ui_base_url: "http://localhost:8001",
    ui_port: 8001,
    debug: false
  },
  performance: {
    api_timeout: 5000,
    polling_interval: 30000,
    pagination_size: 20
  },
  features: {
    enable_dark_mode: true,
    enable_auto_refresh: false,
    enable_notifications: false
  },
  logging: {
    level: "info",
    log_api_requests: false
  },
  auth: {
    username: "dashboard",
    password: "dashboard123"
  }
};
