# Frontend Guide

React + TypeScript UI for SWE Agent.

## Tech Stack

- **React** with hooks
- **TypeScript** for type safety
- **Vite** for dev server and building
- **Tailwind CSS** for styling
- **shadcn/ui** for base components
- **Yarn 4** via Corepack for package management

## Development

Uses **Yarn 4** via Corepack:

```bash
cd ui

# Install Corepack if not present (one-time)
npm install -g corepack

# Enable Yarn (uses version from packageManager field)
corepack enable

# Verify Yarn version (should be 4.x)
yarn --version

# Install and run
yarn install
yarn dev          # http://localhost:8001
```

### Yarn 4 Notes

- **nodeLinker**: Uses `node-modules` mode (classic `node_modules` folder, not Plug'n'Play)
- **Zero-installs**: Yarn manages dependencies via `.yarn/cache`
- **Immutable installs**: Use `--immutable` flag in CI/Docker for reproducible builds
- **Workspaces**: Monorepo support with `yarn workspaces focus` for production installs

**Production dependency install (Docker Stage 2):**
```bash
# Yarn 4 replacement for deprecated 'yarn install --production'
yarn workspaces focus --all --production
```

See [Yarn 4 Documentation](https://yarnpkg.com/blog/release/4.0) for advanced features.

## Configuration

Environment files in `ui/environments/`:

- `env.default` - Base configuration
- `env.dev` - Development overrides
- `env.prod` - Production settings
- `env.{ENV}.local` - Local overrides (git-ignored)

Configuration is loaded at runtime via `/api/config` endpoint in production.

## Project Structure

```
src/
├── components/     # Reusable UI components
│   ├── ui/        # shadcn/ui base components
│   └── layout/    # Layout components
├── pages/         # Route-level pages
├── lib/           # Utilities and API clients
└── assets/        # Static assets
```

## API Integration

The UI fetches configuration from `/api/config` on startup, then makes API calls to the backend.

Environment-specific API URLs:

- dev: http://localhost:8002
- dev_docker: http://swe-agent-api:8000
- stage/prod: Configured via environment

## Production Build

```bash
yarn build        # Creates dist/
yarn start        # Express server for production
```

The Express server:

- Serves static files from `dist/`
- Provides `/api/config` for runtime configuration
- Supports SPA routing (serves index.html for all routes)

## Adding a New Page

1. Create component in `src/pages/YourPage.tsx`
2. Add route in `src/App.tsx`
3. Add navigation link in `Header.tsx` or `Sidebar.tsx`

## AI Hub

The [AI Hub](./ai-hub.md) is a dedicated page showcasing AI tools across the organization:

- **Grid view** of tools by SDLC stage
- **Detail view** with capabilities and limitations
- **Search and filter** by type, team, status
- **Click-to-scroll** navigation from grid to details

Data is sourced from `ui/public/data/ai-tools.json`.

## Component Conventions

Components use `cn()` from `@/lib/utils` for Tailwind class merging:

```tsx
import { cn } from "@/lib/utils";

export const Button = ({ className, ...props }) => (
  <button className={cn("base-classes", className)} {...props} />
);
```

## Troubleshooting

| Issue               | Solution                                  |
| ------------------- | ----------------------------------------- |
| Port 8001 in use    | `lsof -i :8001` then `kill -9 <PID>`      |
| API connection fail | Verify API running at configured URL      |
| Config not loading  | Check `ui/environments/env.*` files exist |
| Module not found    | Delete `node_modules` and `yarn install`  |
