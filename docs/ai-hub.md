# AI Hub Documentation

The AI Hub is a comprehensive dashboard for discovering and exploring AI-powered tools across the Razorpay engineering organization.

## Overview

The AI Hub provides a single-pane view of:
- **26+ AI tools** across the SDLC lifecycle
- **Tool capabilities** (what each tool can do)
- **Current limitations** (what tools cannot do yet)
- **Production readiness** status
- **Team ownership** and points of contact

## Data Structure

Tool data is defined in `ui/public/data/ai-tools.json` and follows the schema defined in `ui/src/types/ai-hub.ts`.

### Tool Schema

```typescript
interface Tool {
  id: string              // URL-safe unique identifier
  stage: string           // SDLC stage (Planning, Coding, Testing, etc.)
  stageEmoji: string      // Visual indicator
  name: string            // Display name
  type: ToolType          // Plugin | MCP | Skill | Agent | Langgraph Agent | Service | Platform | Multi-Agent
  poc: string             // Point of contact
  team: string            // Owning team
  canDo: string[]         // Capabilities
  cantDo: string[]        // Known limitations
  state: string           // Current status
  prodReady: 'Yes' | 'Partially' | 'No' | 'Preview'
  slackChannel?: string   // Support channel
  docsLink?: string       // Documentation URL
}
```

## SDLC Stages

Tools are organized by SDLC stage:

| Stage | Emoji | Description |
|-------|-------|-------------|
| Planning | 📋 | PRD generation, knowledge discovery |
| Coding | 💻 | Design systems, component libraries |
| Devstack | 🧰 | Local development, debugging |
| Testing | 🧪 | E2E tests, SLIT agents, quality |
| Reviews | 👀 | Code review, rCoRe |
| Infra | ⚙️ | MCP servers, infrastructure |
| Deployments | 🚀 | CI/CD, Spinnaker, Tejas |
| Harness | 🎯 | Multi-agent orchestration, cloud agents |

## Tool Types

- **Plugin** - IDE/editor extensions (Claude plugins)
- **MCP** - Model Context Protocol servers
- **Skill** - Reusable agent capabilities
- **Agent** - Autonomous task performers
- **Langgraph Agent** - State-machine based agents (deprecated, migrating to Skills)
- **Service** - Standalone web services
- **Platform** - Multi-tenant infrastructure
- **Multi-Agent** - Orchestration systems

## UI Features

### Grid View
- **Stage sections** - Tools grouped by SDLC stage
- **Tool cards** - Quick overview with type, team, status
- **Click to detail** - Scrolls to detailed view

### Details Section
- **Expandable cards** - Full capabilities and limitations
- **Direct links** - Slack channels, documentation
- **Status indicators** - Production readiness badges

### Search & Filter
- **Text search** - Filter by name, team, POC
- **Type filter** - Show only specific tool types
- **Status filter** - Filter by production readiness

## Adding or Updating Tools

1. Edit `ui/public/data/ai-tools.json`
2. Ensure each tool has a unique `id` (URL-safe slug)
3. Update the `count` and `updated` fields
4. Test locally: `yarn dev` → navigate to AI Hub
5. Verify scroll-to-detail works with the new ID

### ID Conventions

- Use kebab-case: `my-tool-name`
- Match the tool's URL slug if applicable
- Keep stable once published (used for scroll-to-detail)

### Example Addition

```json
{
  "id": "my-new-tool",
  "stage": "Coding",
  "stageEmoji": "💻",
  "name": "My New Tool",
  "type": "Skill",
  "poc": "Jane Doe",
  "team": "DevEx",
  "canDo": [
    "Automates specific task",
    "Integrates with existing workflow"
  ],
  "cantDo": [
    "Cannot handle edge case X",
    "Requires manual intervention for Y"
  ],
  "state": "Beta",
  "prodReady": "Partially",
  "slackChannel": "#my-team",
  "docsLink": "https://github.com/razorpay/..."
}
```

## Architecture

The AI Hub is implemented as a React page component:

```
src/pages/AiHubPage.tsx    # Main page component
src/types/ai-hub.ts         # TypeScript definitions
public/data/ai-tools.json   # Static data source
```

### Key Components

- `StageSection` - Renders tools grouped by SDLC stage
- `ToolCard` - Compact grid view of a tool
- `ToolDetailCard` - Expandable detailed view
- `DetailsSection` - Container for all detail cards

### Scroll-to-Detail Feature

Clicking a tool card in the grid:
1. Calls `scrollToDetail(toolId)` 
2. Sets `openDetailId` state
3. Scrolls to `id="detail-{toolId}"` element
4. Auto-expands the detail card

This enables quick navigation from overview to detailed information.

## Related Documentation

- [Frontend Guide](./frontend.md) - UI development
- [Agents Catalogue](./agents_catalogue/) - Creating AI agents
- [Types](../ui/src/types/ai-hub.ts) - TypeScript definitions
