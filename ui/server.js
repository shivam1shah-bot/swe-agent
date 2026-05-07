import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';
import pino from 'pino';
import pinoRoll from 'pino-roll';
import { getAllConfigs } from './environments/config-loader.server.js';

// Get __dirname equivalent in ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Ensure log directory exists
const LOG_DIR = path.join(process.cwd(), 'tmp', 'logs');
try {
  fs.mkdirSync(LOG_DIR, { recursive: true });
} catch (err) {
  console.error(`Failed to create log directory: ${err.message}`);
}

// Parse command line arguments first (needed for log level)
function parseArgs() {
  const args = process.argv.slice(2);
  const parsed = {};

  // Check for help flag first
  if (args.includes('--help') || args.includes('-h')) {
    console.log(`
Usage: node server.js [options]

Options:
  --port <number>    Port to bind to (default: from config or 8001)
  --host <address>   Host to bind to (default: 0.0.0.0)
  --env <name>       Environment name (default: dev)
  --debug            Enable debug mode
  --log-level <lvl>  Log level (fatal/error/warn/info/debug/trace) [default: info]
  --help, -h         Show this help message

Environment Variables:
  PORT               Override port
  HOST               Override host
  APP_ENV            Override environment
  DEBUG              Set to 'true' to enable debug mode
  NODE_ENV           Set to 'development' to enable debug mode
  LOG_LEVEL          Set log level (fatal/error/warn/info/debug/trace)
`);
    process.exit(0);
  }

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--port' && args[i + 1]) {
      parsed.port = parseInt(args[i + 1], 10);
      i++;
    } else if (arg === '--host' && args[i + 1]) {
      parsed.host = args[i + 1];
      i++;
    } else if (arg === '--env' && args[i + 1]) {
      parsed.env = args[i + 1];
      i++;
    } else if (arg === '--log-level' && args[i + 1]) {
      parsed.logLevel = args[i + 1];
      i++;
    } else if (arg === '--debug') {
      parsed.debug = true;
    } else if (arg.startsWith('--port=')) {
      parsed.port = parseInt(arg.split('=')[1], 10);
    } else if (arg.startsWith('--host=')) {
      parsed.host = arg.split('=')[1];
    } else if (arg.startsWith('--env=')) {
      parsed.env = arg.split('=')[1];
    } else if (arg.startsWith('--log-level=')) {
      parsed.logLevel = arg.split('=')[1];
    }
  }

  return parsed;
}

const cliArgs = parseArgs();

// Determine log level
const isDevelopment = process.env.NODE_ENV === 'development';
const debugMode = cliArgs.debug || process.env.DEBUG === 'true' || isDevelopment;
const logLevel = cliArgs.logLevel || process.env.LOG_LEVEL || (debugMode ? 'debug' : 'info');

// Create Pino logger with multiple transports
// Note: pinoRoll is async - must await it
const fileTransport = await pinoRoll({
  file: path.join(LOG_DIR, 'swe-agent-ui'),
  frequency: 'daily',
  size: '20m',
  mkdir: true
});

// Prevent unhandled stream 'error' events from crashing the process.
// If the log file is unwritable (e.g. CI runner permissions, disk quota),
// the server should continue serving — file logging is non-critical.
fileTransport.on('error', (err) => {
  console.error('[server] Log file transport error (non-fatal, continuing without file logging):', err.message);
});

// Determine if we need pretty printing
const usePrettyPrint = isDevelopment || debugMode;

const logger = pino({
  level: logLevel.toLowerCase(),
  base: { service: 'swe-agent-ui' }
}, pino.multistream([
  // Console output (with pretty print in dev)
  {
    level: logLevel.toLowerCase(),
    stream: usePrettyPrint
      ? (await import('pino-pretty')).default({
          colorize: true,
          translateTime: 'HH:MM:ss Z',
          ignore: 'pid,hostname,service'
        })
      : process.stdout
  },
  // File output (always JSON)
  {
    level: 'debug',
    stream: fileTransport
  }
]));

// Load all environment configurations from env files first
let environmentConfigs;
try {
  environmentConfigs = getAllConfigs();
  logger.info('Successfully loaded environment configurations');
} catch (error) {
  logger.error({ err: error }, 'Failed to load environment configurations');
  logger.error('Please ensure all required env configuration files exist in ui/environments/');
  process.exit(1);
}

// Helper function to get API base URL from environment configurations
function getApiBaseUrl(appEnv) {
  const config = environmentConfigs[appEnv];
  if (config && config.app && config.app.api_base_url) {
    return config.app.api_base_url;
  }
  // Fallback to dev config if environment not found
  return environmentConfigs['dev'].app.api_base_url;
}

// Helper function to get UI port from environment configurations
function getUiPort(appEnv) {
  const config = environmentConfigs[appEnv];
  if (config && config.app && config.app.ui_port) {
    return config.app.ui_port;
  }
  // Fallback to dev config if environment not found
  return environmentConfigs['dev'].app.ui_port || 8001;
}

// Get port from config (CLI args take precedence, then env var, then config, then 8001)
const appEnv = cliArgs.env || process.env.APP_ENV || 'dev';
const configPort = getUiPort(appEnv);
const port = cliArgs.port || process.env.PORT || configPort || 8001;

// Get host (CLI args take precedence, then env var, then default '0.0.0.0')
const host = cliArgs.host || process.env.HOST || '0.0.0.0';

const app = express();

// Request logging middleware
app.use((req, res, next) => {
  const start = Date.now();
  res.on('finish', () => {
    const duration = Date.now() - start;
    logger.info({
      method: req.method,
      url: req.url,
      status: res.statusCode,
      duration: `${duration}ms`
    }, 'HTTP request');
  });
  next();
});

// Serve static files from the dist directory
app.use(express.static('dist'));

// Health check endpoint for container orchestration
// Lightweight check that verifies server is running and can respond
// Matches API health endpoint format for consistency
app.get('/health', (req, res) => {
  res.status(200).json({
    status: 'healthy',
    timestamp: Math.floor(Date.now() / 1000)
  });
});

// API endpoint to provide runtime configuration
app.get('/api/config', (req, res) => {
  const appName = process.env.APP_NAME || 'Kriya';

  // Get the full env configuration for the environment
  const envConfig = environmentConfigs[appEnv] || environmentConfigs['dev'];

  // Enhanced configuration with environment-specific settings from env files
  const config = {
    APP_ENV: appEnv,
    APP_NAME: appName,
    // Add environment-specific API base URL from configs
    API_BASE_URL: getApiBaseUrl(appEnv),
    // Add auth credentials from environment
    AUTH_USERNAME: envConfig.auth?.username || 'dashboard',
    AUTH_PASSWORD: envConfig.auth?.password || 'dashboard123',
    // Add other runtime config as needed
    DEBUG: debugMode,
    VERSION: process.env.GIT_COMMIT_HASH || 'unknown',
    // Include the full environment configuration from env files
    UI_CONFIG: envConfig
  };

  if (debugMode) {
    logger.debug({ environment: appEnv, config }, 'Serving config endpoint');
  }

  res.json(config);
});

// Serve index.html for all other routes (SPA support)
app.get('*splat', (req, res) => {
  res.sendFile(path.join(__dirname, 'dist', 'index.html'));
});

// Error handling middleware
app.use((err, req, res, next) => {
  logger.error({ err }, 'Unhandled error');
  res.status(500).json({ error: 'Internal server error' });
});

app.listen(port, host, () => {
  const portSource = cliArgs.port ? 'CLI arg' : (process.env.PORT ? 'env var' : (configPort ? 'config' : 'default'));
  const hostSource = cliArgs.host ? 'CLI arg' : (process.env.HOST ? 'env var' : 'default');
  const envSource = cliArgs.env ? 'CLI arg' : (process.env.APP_ENV ? 'env var' : 'default');

  logger.info({
    url: `http://${host}:${port}`,
    environment: appEnv,
    envSource,
    host,
    hostSource,
    port,
    portSource,
    apiBaseUrl: getApiBaseUrl(appEnv),
    debug: debugMode,
    logLevel: logger.level,
    logDir: LOG_DIR
  }, 'Kriya UI server started');

  if (debugMode) {
    logger.debug('Debug mode enabled');
  }
});

// Handle graceful shutdown
process.on('SIGTERM', () => {
  logger.info('SIGTERM received, shutting down gracefully');
  fileTransport.flushSync();
  fileTransport.end();
  process.exit(0);
});

process.on('SIGINT', () => {
  logger.info('SIGINT received, shutting down gracefully');
  fileTransport.flushSync();
  fileTransport.end();
  process.exit(0);
});
