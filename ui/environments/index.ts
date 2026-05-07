import { UIEnvironmentConfig, baseConfig } from './config';

// Runtime configuration cache
let runtimeConfig: UIEnvironmentConfig | null = null;

/**
 * Fetch runtime configuration from the server
 */
async function fetchRuntimeConfig(): Promise<{ 
  APP_ENV: string; 
  APP_NAME: string; 
  API_BASE_URL?: string;
  DEBUG?: boolean;
  VERSION?: string;
  UI_CONFIG?: UIEnvironmentConfig;
}> {
  try {
    const response = await fetch('/api/config');
    if (!response.ok) {
      throw new Error(`Failed to fetch config: ${response.status}`);
    }
    const config = await response.json();
    console.log('🔧 [Client] Fetched runtime config:', config);
    return config;
  } catch (error) {
    console.warn('Failed to fetch runtime config, using defaults:', error);
    return { APP_ENV: 'dev', APP_NAME: 'Vyom' };
  }
}

/**
 * Get the current environment configuration based on runtime APP_ENV
 * Falls back to 'default' if APP_ENV is not set or invalid
 */
export async function getEnvironmentConfig(): Promise<UIEnvironmentConfig> {
  if (runtimeConfig) {
    return runtimeConfig;
  }

  // Fetch runtime configuration
  const runtime = await fetchRuntimeConfig();
  const appEnv = runtime.APP_ENV || 'dev';
  
  // Start with TOML configuration from server or fallback to base config
  const config = runtime.UI_CONFIG ? { ...runtime.UI_CONFIG } : { ...baseConfig };
  
  // Override with runtime configuration if available
  if (runtime.APP_NAME) {
    config.app.name = runtime.APP_NAME;
  }
  
  config.app.environment = appEnv;
  
  // Override API base URL from runtime if provided
  if (runtime.API_BASE_URL) {
    config.app.api_base_url = runtime.API_BASE_URL;
    console.log(`🔗 [Client] Using runtime API base URL: ${runtime.API_BASE_URL}`);
  }
  
  // Override debug flag from runtime if provided
  if (typeof runtime.DEBUG === 'boolean') {
    config.app.debug = runtime.DEBUG;
  }
  
  // Cache the configuration
  runtimeConfig = config;
  
  // Log the loaded environment in development
  if (config.app.debug) {
    console.log(`🔧 [Client] UI Environment loaded: ${appEnv}`, config);
  }
  
  return config;
}

/**
 * Synchronous version that returns cached config or base config
 * Use getEnvironmentConfig() for initial loading with runtime overrides
 */
export function getEnvironmentConfigSync(): UIEnvironmentConfig {
  return runtimeConfig || baseConfig;
}

/**
 * Get specific configuration section (async)
 */
export async function getAppConfig() {
  const config = await getEnvironmentConfig();
  return config.app;
}

export async function getPerformanceConfig() {
  const config = await getEnvironmentConfig();
  return config.performance;
}

export async function getFeaturesConfig() {
  const config = await getEnvironmentConfig();
  return config.features;
}

export async function getLoggingConfig() {
  const config = await getEnvironmentConfig();
  return config.logging;
}

/**
 * Synchronous helpers that use cached config
 */
export function getAppConfigSync() {
  return getEnvironmentConfigSync().app;
}

export function getPerformanceConfigSync() {
  return getEnvironmentConfigSync().performance;
}

export function getFeaturesConfigSync() {
  return getEnvironmentConfigSync().features;
}

export function getLoggingConfigSync() {
  return getEnvironmentConfigSync().logging;
}

// Export a function to get the current environment config
export async function getConfig() {
  return await getEnvironmentConfig();
}

// Export types for use in other files
export type { UIEnvironmentConfig, UIAppConfig, UIPerformanceConfig, UIFeaturesConfig, UILoggingConfig, UIAuthConfig } from './config';