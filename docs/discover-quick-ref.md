# Discover Quick Reference

> **Main Guide**: [Discover Integration](./discover.md)  
> **Auth Pattern**: [Service-to-Service Auth](./service_to_service_auth.md)

## Setup

```bash
# Production: Set service password
export AUTH__USERS__DISCOVER_SERVICE="secure-password"
```

```toml
# environments/env.stage.toml
[discover]
backend_url = "https://discover-api.concierge.stage.razorpay.in"

[auth.users]
discover_service = ""  # Uses env var in prod
```

## Testing

```bash
# Test Basic Auth directly
curl -u discover_service:password \
  https://discover-api.../api/v1/tools

# Test via Vyom proxy (with user JWT)
curl https://vyom-api.../api/v1/discover/tools \
  -H "Authorization: Bearer <token>"
```

## Endpoints

Base: `https://vyom-api.../api/v1/discover`

| Endpoint | Method |
|----------|--------|
| `/query/stream` | POST |
| `/sessions/{id}/save` | POST |
| `/sessions/{id}/share` | POST |
| `/credentials/{id}` | GET/POST/DELETE |
| `/tools` | GET |
| `/tools/{id}/status` | GET |
| `/handoff/{id}/attach` | POST |
| `/handoff/pending/{id}` | GET |
| `/feedback/ui` | POST |

## Troubleshooting

| Error | Fix |
|-------|-----|
| 401 | Check `AUTH__USERS__DISCOVER_SERVICE` matches Discover config |
| 503 | Verify `discover.backend_url` is reachable |

---

_Last updated: 2026-03-22_
