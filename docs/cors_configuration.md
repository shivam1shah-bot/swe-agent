# Dynamic CORS Configuration

## Overview

The SWE Agent API uses a flexible CORS (Cross-Origin Resource Sharing) configuration that:

- **Development**: Allows all common localhost ports for maximum development flexibility
- **Staging/Production**: Restricts origins to only specific configured URLs for security

## Configuration Strategy

### 🔓 **Development Mode** (Permissive)

- **Environment**: `dev`, `development`, `dev_docker`
- **Strategy**: Allow common localhost ports on both HTTP and HTTPS
- **Ports Included**: `3000, 3001, 3002, 3003, 5000, 5001, 8000, 8001, 8002, 8080, 8888, 9000`
- **Protocols**: Both `http://` and `https://` for each port
- **Hosts**: Both `localhost` and `127.0.0.1`

### 🔒 **Production/Staging Mode** (Restrictive)

- **Environment**: `stage`, `staging`, `prod`, `production`
- **Strategy**: Only allow specific URLs from environment configuration
- **Sources**: `app.ui_base_url` and optionally `app.api_base_url` (staging only)

## Environment Examples

### Development Environment

**Configuration**:

```toml
[environment]
name = "dev"
```

**Resulting CORS Origins** (48 total):

- `http://localhost:3000`, `https://localhost:3000`
- `http://127.0.0.1:3000`, `https://127.0.0.1:3000`
- `http://localhost:3001`, `https://localhost:3001`
- ... (for all 12 common ports)
- ✨ **Any localhost port works for development flexibility**

### Staging Environment

**Configuration**:

```toml
[app]
ui_base_url = "https://swe-agent.concierge.stage.razorpay.in"
api_base_url = "https://swe-agent-api.concierge.stage.razorpay.in"
```

**Resulting CORS Origins** (2 total):

- `https://swe-agent.concierge.stage.razorpay.in`
- `https://swe-agent-api.concierge.stage.razorpay.in`

### Production Environment

**Configuration**:

```toml
[app]
ui_base_url = "https://swe-agent.prod.razorpay.com"
```

**Resulting CORS Origins** (1 total):

- `https://swe-agent.prod.razorpay.com`

## Benefits

### 🛠️ **Developer Experience**

- **No CORS headaches**: Any localhost port works in development
- **Zero configuration**: Works with Vite, React, Next.js, custom ports
- **HTTPS support**: Works with local SSL certificates

### 🔒 **Production Security**

- **Strict origin control**: Only configured URLs allowed
- **Minimal attack surface**: Fewest possible allowed origins

## Testing

Run the configuration test:

```bash
python3 scripts/test_cors_config.py
```

## Summary

This CORS configuration provides the perfect balance:

- **🔓 Development**: Maximum flexibility with all localhost ports allowed
- **🔒 Production**: Strict security with only configured URLs allowed
- **🚀 Zero Configuration**: Automatically adapts to your environment

Perfect for developer productivity while maintaining production security! 🎯
