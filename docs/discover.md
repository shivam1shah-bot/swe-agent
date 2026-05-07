# Discover Integration

> **Pattern**: [Service-to-Service Auth](./service_to_service_auth.md)  
> **UI Guide**: [UI Integration](./discover-ui-integration.md)  
> **Quick Ref**: [Quick Reference](./discover-quick-ref.md)

Vyom proxies Discover API requests using HTTP Basic Authentication, following the [service-to-service auth pattern](./service_to_service_auth.md).

## Architecture

```
┌─────────┐     User JWT      ┌──────────────┐    Basic Auth      ┌───────────┐
│   UI    │ ────────────────→ │  Vyom API    │ ────────────────→  │ Discover  │
│(Browser)│                   │  (Proxy)     │   + X-User-Email   │ (Backend) │
└─────────┘                   └──────────────┘                    └───────────┘
```

1. **UI** sends user JWT to Vyom API at `/api/v1/discover/*`
2. **Vyom** validates JWT, extracts user email
3. **Vyom** adds service credentials via Basic Auth header
4. **Vyom** forwards user context via `X-User-Email` header
5. **Discover** validates Basic Auth and processes request

## Implementation

### Module Reference

| Component | Module | Purpose |
|-----------|--------|---------|
| API Router | `src.api.routers.discover` | Proxy endpoints, auth header preparation |
| Auth | `src.providers.auth.basic_auth` | Basic Auth validation |
| Config | `src.providers.config_loader` | TOML + env var loading |

### Configuration

```toml
# environments/env.{env}.toml
[discover]
backend_url = "https://discover-api.concierge.stage.razorpay.in"
timeout = 30

[auth.users]
discover_service = ""  # Set via AUTH__USERS__DISCOVER_SERVICE
```

**Environment Variable (production):**
```bash
export AUTH__USERS__DISCOVER_SERVICE="secure-password"
```

### Endpoints

All endpoints are prefixed with `/api/v1/discover/`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/query/stream` | POST | Streaming query |
| `/sessions/{id}/save` | POST | Save conversation |
| `/sessions/{id}/share` | POST | Share conversation |
| `/credentials/{tool_id}` | GET/POST/DELETE | MCP credentials |
| `/tools` | GET | List MCP tools |
| `/tools/{id}/status` | GET | Tool status |
| `/handoff/{ref_id}/attach` | POST | Attach handoff |
| `/handoff/pending/{id}` | GET | Pending messages |
| `/feedback/ui` | POST | Submit feedback |

See [UI Integration](./discover-ui-integration.md) for frontend service details.

## Security

- **Basic Auth**: `Authorization: Basic base64(discover_service:password)`
- **User Context**: Forwarded via `X-User-Email` header (optional)
- **Constant-Time**: Password comparison uses `hmac.compare_digest()`
- **HTTPS**: Required in production (Basic Auth is base64, not encrypted)

See [service-to-service auth patterns](./service_to_service_auth.md) for details on credential management and security best practices.

## Troubleshooting

| Issue | Check |
|-------|-------|
| 401 Auth Failed | `AUTH__USERS__DISCOVER_SERVICE` env var set and matches Discover config |
| 503 Unavailable | `discover.backend_url` reachable from Vyom |

**Test Basic Auth:**
```bash
curl -u discover_service:password \
  https://discover-api.../api/v1/tools
```

**Test Via Proxy:**
```bash
curl https://vyom-api.../api/v1/discover/tools \
  -H "Authorization: Bearer <user_jwt>"
```

## Migration Notes

If migrating from JWT token exchange:

| Before | After |
|--------|-------|
| `[token_exchange]` config | `[auth.users].discover_service` |
| Redis token cache | None needed |
| Direct Discover API calls | Via `/api/v1/discover/*` proxy |

---

_Last updated: 2026-03-22_
