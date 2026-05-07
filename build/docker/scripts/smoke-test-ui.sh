#!/bin/sh
# Smoke tests for UI production image
# This script verifies that the production image has all required dependencies
# and that the server can start and respond to requests.

set -e

echo "=== Running UI smoke tests ==="

# Test 1: Verify critical runtime dependencies exist in node_modules
echo "Test 1: Checking runtime dependencies..."
test -d node_modules/express || (echo "FAIL: express not found in node_modules" && exit 1)
test -d node_modules/pino || (echo "FAIL: pino not found in node_modules" && exit 1)
test -d node_modules/dotenv || (echo "FAIL: dotenv not found in node_modules" && exit 1)
echo "✓ All runtime dependencies present"

# Test 2: Verify built artifacts exist
echo "Test 2: Checking build artifacts..."
test -d dist || (echo "FAIL: dist/ directory not found" && exit 1)
test -f dist/index.html || (echo "FAIL: dist/index.html not found" && exit 1)
test -f server.js || (echo "FAIL: server.js not found" && exit 1)
echo "✓ All build artifacts present"

# Test 3: Verify server can start and respond
echo "Test 3: Starting server and testing /health endpoint..."
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

echo "=== All UI smoke tests passed ==="
