/* eslint-disable @typescript-eslint/no-explicit-any -- TODO: Fix types gradually */
// UI environment configuration utilities with runtime loading
import { 
  getConfig, 
  getAppConfigSync, 
  getPerformanceConfigSync, 
  getFeaturesConfigSync, 
  getLoggingConfigSync,
  getEnvironmentConfigSync
} from '../../environments';

// Initialize configuration (call this in your app startup)
export async function initializeConfig() {
  console.log('🔧 [Environment] Starting configuration initialization...');
  
  try {
    const config = await getConfig();
    console.log('✅ [Environment] Runtime configuration loaded successfully');
    console.log('🔧 [Environment] Environment:', config.app.environment);
    console.log('🔗 [Environment] API Base URL:', config.app.api_base_url);
    console.log('🌐 [Environment] UI Base URL:', config.app.ui_base_url);
    console.log('🐛 [Environment] Debug Mode:', config.app.debug);
    console.log('📊 [Environment] Features:', config.features);
    console.log('📝 [Environment] Logging:', config.logging);
    
    // Validate critical configuration
    if (!config.app.api_base_url) {
      console.warn('⚠️ [Environment] API base URL is not configured!');
    }
    
    if (!config.app.ui_base_url) {
      console.warn('⚠️ [Environment] UI base URL is not configured!');
    }
    
    if (config.app.api_base_url.includes('localhost:8002') && config.app.environment === 'dev_docker') {
      console.error('❌ [Environment] CONFIGURATION ERROR: Docker environment is using localhost:8002 instead of localhost:28002');
      console.error('❌ [Environment] This will cause API calls to fail in Docker environment');
    }
    
    return config;
  } catch (error) {
    console.error('❌ [Environment] Failed to initialize configuration:', error);
    throw error;
  }
}

// Synchronous utility functions for common use cases (use after initialization)
export function getApiBaseUrl(): string {
  return getAppConfigSync().api_base_url;
}



export function getUiBaseUrl(): string {
  return getAppConfigSync().ui_base_url;
}

export function getFullUiUrl(): string {
  const config = getAppConfigSync();
  const baseUrl = config.ui_base_url;
  const port = config.ui_port;
  // If base URL already includes port or is a non-localhost domain, return as-is
  if (baseUrl.includes(':') && !baseUrl.endsWith(':80') && !baseUrl.endsWith(':443')) {
    return baseUrl;
  }
  // For localhost or raw domains, append the port
  return `${baseUrl}:${port}`;
}

export function getEnvironmentName(): string {
  return getAppConfigSync().environment;
}

export function isDebugMode(): boolean {
  return getAppConfigSync().debug;
}

export function getApiTimeout(): number {
  return getPerformanceConfigSync().api_timeout;
}

export function getPollingInterval(): number {
  return getPerformanceConfigSync().polling_interval;
}

export function getPaginationSize(): number {
  return getPerformanceConfigSync().pagination_size;
}

export function isDarkModeEnabled(): boolean {
  return getFeaturesConfigSync().enable_dark_mode;
}

export function isAutoRefreshEnabled(): boolean {
  return getFeaturesConfigSync().enable_auto_refresh;
}

export function areNotificationsEnabled(): boolean {
  return getFeaturesConfigSync().enable_notifications;
}

export function getLogLevel(): string {
  return getLoggingConfigSync().level;
}

export function shouldLogApiRequests(): boolean {
  return getLoggingConfigSync().log_api_requests;
}

export function getUiConfig() {
  return getEnvironmentConfigSync();
}

// Export everything for convenience
export * from '../../environments';

// Logger utility based on environment
export const logger = {
  debug: (...args: any[]) => {
    const loggingConfig = getLoggingConfigSync();
    if (loggingConfig.level === 'debug' && isDebugMode()) {
      console.log('[DEBUG]', ...args);
    }
  },
  info: (...args: any[]) => {
    const loggingConfig = getLoggingConfigSync();
    if (['debug', 'info'].includes(loggingConfig.level)) {
      console.info('[INFO]', ...args);
    }
  },
  warn: (...args: any[]) => {
    const loggingConfig = getLoggingConfigSync();
    if (['debug', 'info', 'warn'].includes(loggingConfig.level)) {
      console.warn('[WARN]', ...args);
    }
  },
  error: (...args: any[]) => {
    console.error('[ERROR]', ...args);
  }
};

// Example usage in components:
/*
// In your main App component or index.tsx:
import { initializeConfig } from './lib/environment';

// Initialize configuration before rendering
await initializeConfig();

// Then use synchronous utilities anywhere:
import { getApiBaseUrl, logger, isDebugMode, getEnvironmentName } from './lib/environment';

// In logging
logger.debug('Component mounted', { props });

// In conditional rendering
{isDebugMode() && <DebugPanel />}

// Show current environment
console.log('Current environment:', getEnvironmentName());
*/ 