# Discover UI Integration

> **Main Guide**: [Discover Integration](./discover.md)  
> **Auth Pattern**: [Service-to-Service Auth](./service_to_service_auth.md)

Discover UI services call Discover endpoints through the Vyom API proxy.

## Architecture

```
UI Services → getApiBaseUrl() → Vyom API (/api/v1/discover/*) → Discover Backend
```

## Frontend Services

| Service | Module | Description |
|---------|--------|-------------|
| Query | `ui.src.services.discover.discover` | Streaming queries |
| Conversation | `ui.src.services.discover.conversation` | Save/share |
| Credentials | `ui.src.services.discover.credentials` | MCP credentials |
| Tools | `ui.src.services.discover.tools` | MCP tools |
| Handoff | `ui.src.services.discover.handoff` | Handoff operations |

All services use `getApiBaseUrl()` and prefix endpoints with `/api/v1/discover/`.

## Endpoints

| UI Endpoint | Proxies To |
|-------------|------------|
| `POST /api/v1/discover/query/stream` | `POST /api/v1/query/stream` |
| `POST /api/v1/discover/sessions/{id}/save` | `POST /api/v1/sessions/{id}/save` |
| `POST /api/v1/discover/sessions/{id}/share` | `POST /api/v1/sessions/{id}/share` |
| `GET /api/v1/discover/credentials/{id}` | `GET /api/v1/credentials/{id}` |
| `POST /api/v1/discover/credentials` | `POST /api/v1/credentials` |
| `DELETE /api/v1/discover/credentials/{id}` | `DELETE /api/v1/credentials/{id}` |
| `GET /api/v1/discover/tools` | `GET /api/v1/tools` |
| `GET /api/v1/discover/tools/{id}/status` | `GET /api/v1/tools/{id}/status` |
| `POST /api/v1/discover/handoff/{id}/attach` | `POST /api/v1/handoff/{id}/attach` |
| `GET /api/v1/discover/handoff/pending/{id}` | `GET /api/v1/handoff/pending/{id}` |
| `POST /api/v1/discover/feedback/ui` | `POST /api/v1/feedback/ui` |

## Configuration

```bash
# ui/environments/env.{env}
APP_API_BASE_URL="https://vyom-api.concierge.stage.razorpay.in"
```

Note: `APP_DISCOVER_API_BASE_URL` is deprecated. Discover now uses the main API via proxy.

## Error Handling

Service errors include HTTP status:

```typescript
import { ConversationServiceError } from "@/services/discover/conversation";

try {
  await conversationService.save(sessionId, transcript);
} catch (err) {
  if (err instanceof ConversationServiceError && err.status === 401) {
    // Handle auth error
  }
}
```

## Testing

```bash
# Test proxy endpoint
curl https://vyom-api.../api/v1/discover/tools \
  -H "Authorization: Bearer <user_jwt>"
```

---

_Last updated: 2026-03-22_
