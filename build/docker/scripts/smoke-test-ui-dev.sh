#!/bin/sh
# Smoke tests for UI development image
# This script verifies that the development image has all required dependencies
# and that the dev server can start.

set -e

echo "=== Running UI dev smoke tests ==="

# Test 1: Verify all dependencies exist in node_modules (dev + prod)
echo "Test 1: Checking all dependencies..."
test -d node_modules/express || (echo "FAIL: express not found in node_modules" && exit 1)
test -d node_modules/pino || (echo "FAIL: pino not found in node_modules" && exit 1)
test -d node_modules/dotenv || (echo "FAIL: dotenv not found in node_modules" && exit 1)
test -d node_modules/vite || (echo "FAIL: vite not found in node_modules (dev dependency)" && exit 1)
test -d node_modules/typescript || (echo "FAIL: typescript not found in node_modules (dev dependency)" && exit 1)
echo "✓ All dependencies present (including dev)"

# Test 2: Verify source files exist
echo "Test 2: Checking source files..."
test -f vite.config.ts || (echo "FAIL: vite.config.ts not found" && exit 1)
test -d src || (echo "FAIL: src/ directory not found" && exit 1)
test -f src/App.tsx || (echo "FAIL: src/App.tsx not found" && exit 1)
echo "✓ Source files present"

# Test 3: Verify build works
echo "Test 3: Testing production build..."
yarn build || (echo "FAIL: Build failed" && exit 1)
test -d dist || (echo "FAIL: dist/ not created after build" && exit 1)
test -f dist/index.html || (echo "FAIL: dist/index.html not created after build" && exit 1)
echo "✓ Build successful"

# Test 4: Verify production server can start (uses the built dist/)
echo "Test 4: Testing production server startup..."
node -e "
const http = require('http');
const { spawn } = require('child_process');
const server = spawn('node', ['server.js', '--port', '9999'], { stdio: 'inherit' });
let passed = false;
let checkInterval;
const checkServer = () => {
    http.get('http://localhost:9999/health', (res) => {
        if (res.statusCode === 200) {
            console.log('✓ Server starts and responds to /health');
            passed = true;
            clearInterval(checkInterval);
            server.kill();
        } else {
            console.log('FAIL: Unexpected status:', res.statusCode);
            clearInterval(checkInterval);
            server.kill();
        }
    }).on('error', () => {
        // Server not ready yet, retry on next interval tick
    });
};
checkInterval = setInterval(checkServer, 1000);
setTimeout(() => {
    if (!passed) {
        console.log('FAIL: Timeout waiting for server');
        clearInterval(checkInterval);
        server.kill();
    }
}, 8000);
server.on('exit', () => process.exit(passed ? 0 : 1));
"

echo "=== All UI dev smoke tests passed ==="
