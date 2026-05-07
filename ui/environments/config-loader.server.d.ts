/**
 * Configuration structure interface
 */
export interface UIConfig {
  app: {
    name: string;
    environment: string;
    api_base_url: string;
    ui_base_url: string;
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

/**
 * Load configuration from env file (server-side only)
 */
export function loadConfigFromEnv(environment: string): UIConfig;

/**
 * Load configuration based on NODE_ENV or APP_ENV (server-side only)  
 */
export function loadCurrentConfig(): UIConfig;

/**
 * Get all available environment configurations (server-side only)
 */
export function getAllConfigs(): Record<string, UIConfig>;

/**
 * Clear configuration cache (useful for testing)
 */
export function clearConfigCache(): void; 