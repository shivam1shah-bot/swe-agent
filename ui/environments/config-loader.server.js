import { config } from 'dotenv';
import { existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

// Get __dirname equivalent in ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Cache for loaded configurations
const configCache = new Map();

/**
 * Parse environment variables into structured config object
 */
function parseEnvToConfig(envVars) {
  const configObj = {
    app: {},
    performance: {},
    features: {},
    logging: {},
    auth: {}
  };

  for (const [key, value] of Object.entries(envVars)) {
    const [section, ...keyParts] = key.toLowerCase().split('_');
    const configKey = keyParts.join('_');

    // Convert string values to appropriate types
    let parsedValue = value;
    if (value === 'true') parsedValue = true;
    else if (value === 'false') parsedValue = false;
    else if (/^\d+$/.test(value)) parsedValue = parseInt(value, 10);
    else if (/^\d+\.\d+$/.test(value)) parsedValue = parseFloat(value);
    // Remove quotes if present
    else if (typeof value === 'string' && value.startsWith('"') && value.endsWith('"')) {
      parsedValue = value.slice(1, -1);
    }

    if (configObj[section]) {
      configObj[section][configKey] = parsedValue;
    }
  }

  return configObj;
}

/**
 * Load environment variables from a specific env file using dotenv
 */
function loadEnvFile(filePath) {
  if (!existsSync(filePath)) {
    throw new Error(`Environment file not found: ${filePath}`);
  }

  // Use dotenv to load the environment file
  const result = config({ path: filePath });
  
  if (result.error) {
    throw new Error(`Failed to load environment file: ${result.error.message}`);
  }

  return result.parsed || {};
}

/**
 * Deep merge two configuration objects
 */
function deepMerge(base, override) {
  const result = { ...base };
  
  for (const key in override) {
    if (override[key] && typeof override[key] === 'object' && !Array.isArray(override[key])) {
      result[key] = deepMerge(base[key] || {}, override[key]);
    } else {
      result[key] = override[key];
    }
  }
  
  return result;
}

/**
 * Load configuration from env file (server-side only)
 */
export function loadConfigFromEnv(environment) {
  // Check cache first
  if (configCache.has(environment)) {
    return configCache.get(environment);
  }

  try {
    // Load default configuration first
    const defaultConfigPath = join(__dirname, 'env.default');
    const defaultEnvVars = loadEnvFile(defaultConfigPath);
    const defaultConfig = parseEnvToConfig(defaultEnvVars);
    
    // If requesting default environment, return it directly
    if (environment === 'default') {
      configCache.set(environment, defaultConfig);
      return defaultConfig;
    }
    
    // Load environment-specific configuration
    const envConfigPath = join(__dirname, `env.${environment}`);
    const envVars = loadEnvFile(envConfigPath);
    const envConfig = parseEnvToConfig(envVars);
    
    // Merge default with environment-specific overrides
    const mergedConfig = deepMerge(defaultConfig, envConfig);
    
    // Cache the configuration
    configCache.set(environment, mergedConfig);
    
    return mergedConfig;
  } catch (error) {
    console.error(`Failed to load env config for environment: ${environment}`, error);
    throw new Error(`Configuration files missing: Could not load env.${environment} or env.default. Please ensure environment configuration files exist.`);
  }
}

/**
 * Load configuration based on NODE_ENV or APP_ENV (server-side only)
 */
export function loadCurrentConfig() {
  const environment = process.env.APP_ENV || process.env.NODE_ENV || 'dev';
  return loadConfigFromEnv(environment);
}

/**
 * Get all available environment configurations (server-side only)
 * @throws {Error} If no configurations can be loaded
 */
export function getAllConfigs() {
  const environments = ['default', 'dev', 'dev_docker', 'stage', 'prod'];
  const configs = {};
  const errors = [];
  
  for (const env of environments) {
    try {
      configs[env] = loadConfigFromEnv(env);
    } catch (error) {
      console.warn(`Failed to load config for environment: ${env}`);
      errors.push({ environment: env, error: error.message });
    }
  }
  
  // If no configurations were loaded successfully, fail
  if (Object.keys(configs).length === 0) {
    console.error('❌ No environment configurations could be loaded');
    throw new Error(`Configuration loading failed: Unable to load any environment configurations. Errors: ${errors.map(e => `${e.environment}: ${e.error}`).join('; ')}`);
  }
  
  // If default config is missing (which is critical), fail even if other configs loaded
  if (!configs.default) {
    console.error('❌ Default configuration is missing - this is required for the system to work');
    throw new Error('Critical configuration missing: env.default is required but could not be loaded. Please ensure this file exists.');
  }
  
  return configs;
}

/**
 * Clear configuration cache (useful for testing)
 */
export function clearConfigCache() {
  configCache.clear();
}
