import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { loadConfigFromEnv } from './environments/config-loader.server.js'
import type { UIEnvironmentConfig } from './environments/config.ts'

// Note: Runtime configuration is loaded from env files via /api/config endpoint
// This build-time configuration loads values directly from env files

// Helper function to get API base URL from env files
function getApiBaseUrl(appEnv: string): string {
  try {
    const config = loadConfigFromEnv(appEnv);
    return config.app.api_base_url;
  } catch (_error) {
    const errorMessage = _error instanceof Error ? _error.message : String(_error);
    throw new Error(`Failed to load API base URL for environment: ${appEnv}. ${errorMessage}`);
  }
}

// Helper function to get UI port from env files
function getUiPort(appEnv: string): number {
  try {
    const config = loadConfigFromEnv(appEnv) as UIEnvironmentConfig;
    return config.app.ui_port || 8001;
  } catch (_error) {
    return 8001;
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- Config return type is intentionally flexible
function getFullConfig(appEnv: string): any {
  try {
    return loadConfigFromEnv(appEnv);
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    throw new Error(`Failed to load full config for environment: ${appEnv}. ${errorMessage}`);
  }
}

// Get environment and port
const appEnv = process.env.APP_ENV || 'dev';
const uiPort = getUiPort(appEnv);
// Use actual server port (important for Docker where external and internal ports differ)
const serverPort = parseInt(process.env.PORT || String(uiPort));

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    rollupOptions: {
      external: [],
      output: {
        manualChunks: (id) => {
          if (id.includes('recharts')) {
            return 'recharts';
          }
          return null;
        },
      },
    },
    target: 'es2020',
    minify: false,
  },
  optimizeDeps: {
    include: ['react', 'react-dom'],
    exclude: []
  },
  server: {
    port: serverPort,
    host: process.env.HOST || '0.0.0.0',
    proxy: {
      '/api/config': {
        target: `http://localhost:${serverPort}`,
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq, req, res) => {
            if (req.url === '/api/config') {
              proxyReq.destroy();
              
              const apiBaseUrl = getApiBaseUrl(appEnv);
              const envConfig = getFullConfig(appEnv);
              
              const config = {
                APP_ENV: appEnv,
                APP_NAME: process.env.APP_NAME || 'Vyom',
                API_BASE_URL: apiBaseUrl,
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                AUTH_USERNAME: (envConfig as any).auth?.username || 'dashboard',
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                AUTH_PASSWORD: (envConfig as any).auth?.password || 'dashboard123',
                DEBUG: process.env.NODE_ENV === 'development' || envConfig.app.debug,
                VERSION: process.env.GIT_COMMIT_HASH || 'dev',
                UI_CONFIG: envConfig
              };
              
              console.log(`🔧 [Vite] Serving dev config for environment: ${appEnv}`, config);
              
              res.writeHead(200, {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET',
                'Access-Control-Allow-Headers': 'Content-Type',
              });
              res.end(JSON.stringify(config));
            }
          });
        }
      }
    }
  },
  preview: {
    port: serverPort,
    host: process.env.HOST || '0.0.0.0',
  },
})
