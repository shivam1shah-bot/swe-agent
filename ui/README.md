# UI Quick Reference Guide

Quick start and component reference for the SWE Agent React frontend.

For complete documentation, see: [Frontend Guide](../docs/frontend.md)

## Quick Start

Uses **Yarn** via Corepack:

```bash
# Install Corepack if not present (one-time)
npm install -g corepack

# Enable Yarn (uses version from packageManager field)
corepack enable

# Install dependencies
yarn install

# Start development server (Vite)
yarn dev

# Build for production
yarn build

# Start production server (Express)
yarn start
# Or with custom options:
# yarn start --port 9000 --debug
```

**Access**: http://localhost:8001 (local) or http://localhost:28001 (Docker)

For detailed CLI options and production deployment, see the [Frontend Guide](../docs/frontend.md#production-server).

## Features Overview

### Home Page

- Universal search with engineering categories
- Quick action cards for common workflows
- Recent tasks with status badges
- Workflow statistics dashboard
- System health indicators

### Agents Catalogue

- Featured use cases
- Advanced search and filtering
- Responsive card grid layout
- Detailed listings with metadata
- Edit/view/delete actions

## Design System

**Tech Stack**: React, TypeScript, Vite, Tailwind CSS, shadcn/ui, Lucide React

**Color Scheme**:

- **Primary**: Blue tones for actions/branding
- **Success**: Green for positive states
- **Warning**: Yellow/Orange for experimental states
- **Error**: Red for errors/danger
- **Muted**: Gray for secondary info

## Component Usage Examples

### Button

```tsx
import { Button } from "@/components/ui/button";

<Button variant="default" size="lg">Primary Action</Button>
<Button variant="outline" size="sm">Secondary Action</Button>
<Button variant="destructive">Delete</Button>
<Button variant="ghost" size="icon"><Search /></Button>
```

### Card

```tsx
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";

<Card>
  <CardHeader>
    <CardTitle>Card Title</CardTitle>
    <CardDescription>Card description</CardDescription>
  </CardHeader>
  <CardContent>Card content goes here</CardContent>
</Card>;
```

### Badge

```tsx
import { Badge } from "@/components/ui/badge";

<Badge variant="default">Active</Badge>
<Badge variant="success">Completed</Badge>
<Badge variant="warning">Experimental</Badge>
<Badge variant="destructive">Deprecated</Badge>
```

### Input

```tsx
import { Input } from "@/components/ui/input";

<Input placeholder="Search agents..." />
<Input type="password" placeholder="Enter password" />
<Input disabled placeholder="Disabled input" />
```

### Form (with React Hook Form + Zod)

```tsx
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Form,
  FormField,
  FormItem,
  FormLabel,
  FormControl,
  FormMessage,
} from "@/components/ui/form";

const schema = z.object({
  name: z.string().min(1, "Name is required"),
  email: z.string().email("Invalid email"),
});

const form = useForm({
  resolver: zodResolver(schema),
  defaultValues: { name: "", email: "" },
});

<Form {...form}>
  <form onSubmit={form.handleSubmit(onSubmit)}>
    <FormField
      control={form.control}
      name="name"
      render={({ field }) => (
        <FormItem>
          <FormLabel>Name</FormLabel>
          <FormControl>
            <Input placeholder="John Doe" {...field} />
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  </form>
</Form>;
```

## Project Structure

```
src/
├── components/
│   ├── ui/              # Reusable shadcn/ui components
│   └── layout/          # Layout components (Header, Sidebar)
├── pages/               # Page components
├── lib/
│   └── utils.ts         # Utility functions
├── App.tsx              # Root component
└── index.css            # Global styles
```

## Environment Configuration

The UI uses layered configuration from `environments/`:

- `env.default` - Base configuration
- `env.dev` - Local development settings
- `env.dev_docker` - Docker settings
- `env.stage` - Staging settings
- `env.prod` - Production settings

See [Environment Config System](./environments/README.md) for details.

## API Integration

Configuration is loaded at runtime from `/api/config`:

```typescript
// After app initializes, config is available
const apiBaseUrl = window.CONFIG?.API_BASE_URL;
const enableDarkMode = window.CONFIG?.UI_CONFIG?.features?.enable_dark_mode;
```

## Troubleshooting

**Port already in use?**

```bash
lsof -i :8001
kill -9 $(lsof -t -i:8001)
```

**Permission errors?**

```bash
sudo chown -R $(whoami) ~/.npm
```

**Missing dependencies?**

```bash
rm -rf node_modules yarn.lock
yarn install
```

## Next Steps

📖 Read the [complete frontend guide](../docs/frontend.md) for:

- Detailed setup instructions
- Production deployment
- Development workflows
- Troubleshooting guide
- Best practices

🔗 **API Documentation**: http://localhost:28002/docs (when running)
