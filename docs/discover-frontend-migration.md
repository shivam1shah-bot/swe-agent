# Discover Frontend Migration Plan

> **Navigation**: [Docs Home](./README.md) → [Integration Guide](./discover.md) → [Quick Reference](./discover-quick-ref.md) → [UI Integration](./discover-ui-integration.md) → **Frontend Migration**
>
> **Purpose**: Visual identity, component patterns, and migration steps for the Discover UI.

## Overview

This document outlines the migration of the **Discover** frontend into the **SWE Agent** project as an additional route/tab, with **strict adherence to SWE Agent's visual identity**.

---

## SWE Agent Visual Identity Reference

### Color System (CSS Variables)

```css
/* Dark Mode (Primary) */
--background: 224 71% 8% /* Deep blue-black #0a0f1e */ --foreground: 213 31% 91%
  /* Light gray-white */ --card: 224 71% 8% /* Same as background */
  --card-foreground: 213 31% 91% --primary: 210 40% 98% /* Near white */
  --primary-foreground: 222.2 47.4% 11.2% --muted: 223 47% 15%
  /* Muted blue-gray */ --muted-foreground: 215.4 16.3% 65% --accent: 216 34%
  17% /* Accent blue-gray */ --accent-foreground: 210 40% 98% --border: 216 34%
  17% /* Subtle borders */ --input: 216 34% 17% --ring: 212.7 26.8% 83.9%;
```

### Component Patterns

| Component       | SWE Agent Pattern                                                  |
| --------------- | ------------------------------------------------------------------ |
| **Cards**       | `rounded-xl border bg-card/60 backdrop-blur-md shadow-sm`          |
| **Buttons**     | CVA variants: `default`, `outline`, `ghost`, `secondary`           |
| **Inputs**      | `rounded-md border border-input bg-transparent px-3 py-1`          |
| **Badges**      | CVA variants: `default`, `secondary`, `success`, `warning`, `info` |
| **Text**        | `text-foreground` (primary), `text-muted-foreground` (secondary)   |
| **Backgrounds** | `bg-background` (page), `bg-card/60` (glass panels)                |
| **Borders**     | `border-border` (standard), `border-white/10` (subtle dark mode)   |

### Key Design Principles

1. **Glassmorphism**: `backdrop-blur-md` with semi-transparent backgrounds (`bg-card/60`)
2. **Subtle Gradients**: Low opacity only (`from-blue-500/20`), no strong gradients
3. **Rounded Corners**: `rounded-xl` for cards, `rounded-md` for inputs/buttons
4. **Dark First**: Design for dark mode primarily, light mode secondary
5. **3D Background**: The existing `Background3D` component provides ambient visual interest

---

## High-Level Features

### 1. **Conversational AI Search Interface**

- Natural language query input with keyboard shortcuts (Cmd+K)
- Real-time streaming responses via Server-Sent Events (SSE)
- Support for follow-up questions with session continuity
- Typing indicators and processing status

### 2. **Chat History & Persistence**

- Local storage-based chat history (max 50 conversations)
- Chat entries with title, timestamp, and session ID
- Resume previous conversations from history
- Clear/reset chat history functionality

### 3. **Multi-Source Search Results**

- Search across GitHub, Google Drive, Slack, AWS, and 10+ data sources
- Code reference citations in responses
- Documentation links panel
- Thinking/reasoning blocks display

### 4. **Agent Selection (Planned Feature)**

- UI placeholder for selecting specific domain agents
- Agents for payments, platform, data, frontend, devops, etc.
- Tooltips explaining agent selection benefits

### 5. **Authentication System**

- Google OAuth 2.0 with JWT (HS256)
- Restricted to @razorpay.com domain
- Protected routes with auth guards
- User profile display with avatar

### 6. **Settings & Configuration**

- **Credentials Management**: Add/update/delete MCP tool credentials
- **Connection Status**: Monitor and test tool connections
- **Account Information**: User profile display

### 7. **Save & Share Conversations**

- Save conversations to backend (14-day expiry)
- Generate shareable links (7-day expiry)
- Copy link to clipboard functionality
- Requires authentication

### 8. **Handoff & Deep Links**

- Handoff from Slack with session restoration
- Share conversation via URL (`/share/:shareId`)
- Bootstrap key system for cross-platform resume

### 9. **Tools Grid & Status Dashboard**

- Visual grid of connected MCP tools
- Tool status badges (connected, error, needs_credentials)
- Category filtering (infrastructure, development, monitoring, etc.)
- Last sync time and latency display

### 10. **Feedback System**

- Thumbs up/down on assistant messages
- Feedback submission to backend
- Visual state management for voted messages

---

## Migration Plans with Visual Identity Mapping

### Feature 1: Conversational AI Search Interface

**Current Discover Implementation:**

- Custom gradient backgrounds (`from-[#0b1120] via-[#0f172a]`)
- Ambient gradient orbs with blur effects
- Custom-styled buttons with gradients

**SWE Agent Migration:**

| Discover Element                  | SWE Agent Equivalent                                 |
| --------------------------------- | ---------------------------------------------------- |
| `bg-gradient-to-b from-[#0b1120]` | `bg-background`                                      |
| Ambient gradient orbs             | Remove (3D Background provides visual interest)      |
| `border-white/[0.06]`             | `border-border` or `border-white/10`                 |
| `text-slate-100`                  | `text-foreground`                                    |
| `text-slate-400`                  | `text-muted-foreground`                              |
| `bg-slate-800/50`                 | `bg-card/60 backdrop-blur-md`                        |
| `rounded-2xl`                     | `rounded-xl`                                         |
| Custom gradient buttons           | `Button` component with `default`/`outline` variants |
| `focus:border-cyan-400/40`        | `focus-visible:ring-1 focus-visible:ring-ring`       |

**Implementation:**

```tsx
// SearchBar - SWE Agent styled
<div className="max-w-4xl mx-auto px-4 mb-12">
  <form onSubmit={handleSearch}>
    <div className="relative flex items-center rounded-xl border border-input bg-card/60 backdrop-blur-md shadow-sm focus-within:ring-1 focus-within:ring-ring">
      <Search className="absolute left-4 h-5 w-5 text-muted-foreground" />
      <Input
        className="border-0 bg-transparent pl-12 py-5 text-lg focus-visible:ring-0"
        placeholder="Search across GitHub, Google Drive, Slack, AWS..."
      />
      <kbd className="absolute right-4 hidden md:flex items-center gap-1 px-2 py-1 text-xs font-medium text-muted-foreground bg-muted rounded border">
        <Command className="h-3 w-3" />
        <span>K</span>
      </kbd>
    </div>
  </form>
</div>
```

**Files to Create:**

```
ui/src/pages/DiscoverPage.tsx
ui/src/components/discover/SearchBar.tsx
ui/src/components/discover/ChatInput.tsx
ui/src/components/discover/ChatMessageBubble.tsx
ui/src/components/discover/ChatSidebar.tsx
ui/src/services/discover.service.ts
ui/src/types/discover.ts
```

**Effort:** Medium (3-4 days)

---

### Feature 2: Chat History & Persistence

**Visual Mapping:**

| Discover Element            | SWE Agent Equivalent       |
| --------------------------- | -------------------------- |
| `text-slate-500`            | `text-muted-foreground`    |
| `hover:bg-slate-800/50`     | `hover:bg-accent`          |
| `text-slate-300`            | `text-foreground`          |
| `text-slate-600`            | `text-muted-foreground`    |
| `border-slate-700/40`       | `border-border`            |
| `group-hover:text-cyan-400` | `group-hover:text-primary` |

**Implementation:**

```tsx
// ChatHistory item - SWE Agent styled
<button className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left hover:bg-accent transition-colors group border border-transparent">
  <MessageSquare className="h-4 w-4 flex-shrink-0 text-muted-foreground group-hover:text-primary transition-colors" />
  <span className="flex-1 text-sm text-foreground truncate">
    {entry.title || entry.query}
  </span>
  <span className="flex-shrink-0 text-xs text-muted-foreground">
    {formatRelativeTime(entry.timestamp)}
  </span>
</button>
```

**Files to Create:**

```
ui/src/utils/discover-chat-history.ts
ui/src/components/discover/ChatHistory.tsx
ui/src/components/discover/ChatSidebar.tsx
```

**Effort:** Low (1-2 days)

---

### Feature 3: Multi-Source Search Results

**Visual Mapping:**

| Discover Element             | SWE Agent Equivalent          |
| ---------------------------- | ----------------------------- |
| `bg-slate-800/60`            | `bg-card/60 backdrop-blur-md` |
| `border-slate-700/50`        | `border`                      |
| `text-slate-100`             | `text-foreground`             |
| User avatar bg `bg-blue-600` | `bg-primary`                  |
| Code block `bg-slate-900`    | `bg-muted`                    |
| `rounded-xl`                 | `rounded-xl` (keep)           |

**Implementation Notes:**

- Use existing `react-markdown` setup from SWE Agent
- Port `ThinkingBlock` as `Collapsible` using similar disclosure pattern
- Code references panel uses `Card` with `bg-card/60 backdrop-blur-md`
- Syntax highlighting uses muted backgrounds

**Files to Create:**

```
ui/src/components/discover/CodeRefsPanel.tsx
ui/src/components/discover/DocLinksPanel.tsx
ui/src/components/discover/ThinkingBlock.tsx
```

**Effort:** Medium (2-3 days)

---

### Feature 4: Agent Selection (UI Placeholder)

**Implementation:**

```tsx
// Agent selector placeholder - SWE Agent styled
<div className="flex justify-center">
  <Button variant="outline" disabled className="gap-2">
    <span>⚙️</span>
    <span>Select Agents</span>
    <Badge variant="secondary">Coming Soon</Badge>
  </Button>
</div>
```

**Effort:** Low (0.5 days)

---

### Feature 5: Authentication System

**Reuse Existing:** SWE Agent already has `AuthGuard`, theme-aware login page

**Files to Modify:**

```
ui/src/components/auth/AuthGuard.tsx (extend if needed for Discover-specific auth)
```

**Effort:** Low (1 day) - mostly reuse existing

---

### Feature 6: Settings & Configuration

**Visual Mapping:**

| Discover Element      | SWE Agent Equivalent                                      |
| --------------------- | --------------------------------------------------------- |
| `bg-slate-800/50`     | `bg-card/60 backdrop-blur-md`                             |
| `border-slate-700/50` | `border`                                                  |
| `text-white`          | `text-foreground`                                         |
| `text-slate-400`      | `text-muted-foreground`                                   |
| Status badge colors   | Use `Badge` variants: `success`, `warning`, `destructive` |
| Tab navigation        | Use existing `Tabs` component                             |

**Implementation:**

```tsx
// Credential card - SWE Agent styled
<Card>
  <CardHeader className="flex flex-row items-start justify-between space-y-0">
    <div className="flex items-start gap-3">
      <span className="text-2xl">{tool.icon}</span>
      <div>
        <CardTitle className="text-base">{tool.displayName}</CardTitle>
        <CardDescription>Auth Type: {tool.authType}</CardDescription>
        <div className="mt-2">
          <Badge variant={credential ? "success" : "warning"}>
            {credential ? "Connected" : "Needs Credentials"}
          </Badge>
        </div>
      </div>
    </div>
    <div className="flex gap-2">
      <Button variant="outline" size="sm">
        Update
      </Button>
      <Button variant="ghost" size="sm">
        <Trash2 className="h-4 w-4 text-destructive" />
      </Button>
    </div>
  </CardHeader>
</Card>
```

**Files to Create:**

```
ui/src/components/settings/DiscoverCredentials.tsx
ui/src/components/settings/DiscoverConnections.tsx
ui/src/services/credentials.service.ts
ui/src/context/ToolsContext.tsx
```

**Files to Modify:**

- Extend existing settings page or create `/discover/settings` route

**Effort:** Medium (3-4 days)

---

### Feature 7: Save & Share Conversations

**Implementation:**

```tsx
// Header with save/share - SWE Agent styled
<header className="flex-shrink-0 border-b bg-card/60 backdrop-blur-md">
  <div className="px-6 py-3 flex items-center gap-3">
    <Button variant="ghost" size="sm" onClick={() => navigate("/")}>
      <ArrowLeft className="h-4 w-4" />
    </Button>
    <div className="flex items-center gap-2">
      <Telescope className="h-5 w-5" />
      <h1 className="text-sm font-semibold">Discover</h1>
    </div>
    <div className="ml-auto flex items-center gap-1">
      <Button
        variant="ghost"
        size="sm"
        onClick={handleSave}
        disabled={!canSaveOrShare}
        title="Save conversation (14 days)"
      >
        <Save className="h-4 w-4" />
      </Button>
      <Button
        variant="ghost"
        size="sm"
        onClick={handleShare}
        disabled={!canSaveOrShare}
        title="Share read-only link (7 days)"
      >
        <Share2 className="h-4 w-4" />
      </Button>
    </div>
  </div>
</header>
```

**Files to Create:**

```
ui/src/services/conversation.service.ts
```

**Files to Modify:**

```
ui/src/components/discover/ChatHeader.tsx (with save/share buttons)
```

**Effort:** Low-Medium (2 days)

---

### Feature 8: Handoff & Deep Links

**Visual Mapping:**

- Use same card/button patterns as main interface
- Loading states use existing `Spinner` or `Progress` components
- Error states use `Alert` component

**Files to Create:**

```
ui/src/pages/DiscoverHandoff.tsx
ui/src/pages/DiscoverShare.tsx
ui/src/utils/session-cache.ts
```

**Effort:** Medium (2-3 days)

---

### Feature 9: Tools Grid & Status Dashboard

**Implementation:**

```tsx
// Tools grid - SWE Agent styled
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
  {tools.map((tool) => (
    <Card key={tool.id} className="hover:border-primary/50 transition-colors">
      <CardHeader className="space-y-3">
        <div className="flex items-start justify-between">
          <span className="text-2xl">{tool.icon}</span>
          <Badge variant={getStatusVariant(tool.status)}>
            {tool.status}
          </Badge>
        </div>
        <CardTitle className="text-base">{tool.displayName}</CardTitle>
        <CardDescription>{tool.description}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Last checked: {formatRelativeTime(tool.lastSync)}</span>
          {tool.latency && <span>{tool.latency}ms</span>}
        </div>
      </CardContent>
    </Card>
  ))}
</div>

// Category filter - SWE Agent styled
<div className="flex flex-wrap gap-2 mb-6">
  {categories.map((category) => (
    <Button
      key={category}
      variant={selectedCategory === category ? "default" : "outline"}
      size="sm"
      onClick={() => setSelectedCategory(category)}
    >
      {category === "all" ? `All (${tools.length})` : category}
    </Button>
  ))}
</div>
```

**Files to Create:**

```
ui/src/pages/DiscoverToolsPage.tsx
ui/src/components/discover/ToolCard.tsx
ui/src/components/discover/ToolStatusBadge.tsx
ui/src/context/ToolsContext.tsx
ui/src/services/tools.service.ts
```

**Effort:** Medium (2-3 days)

---

### Feature 10: Feedback System

**Implementation:**

```tsx
// Feedback buttons - SWE Agent styled
<div className="flex items-center gap-1 mt-2">
  <Button
    variant="ghost"
    size="icon"
    className={cn("h-7 w-7", voted === "thumbs_up" && "text-primary")}
    onClick={() => submit("thumbs_up")}
    disabled={submitting}
  >
    <ThumbsUp className="h-4 w-4" />
  </Button>
  <Button
    variant="ghost"
    size="icon"
    className={cn("h-7 w-7", voted === "thumbs_down" && "text-destructive")}
    onClick={() => submit("thumbs_down")}
    disabled={submitting}
  >
    <ThumbsDown className="h-4 w-4" />
  </Button>
</div>
```

**Files to Modify:**

```
ui/src/components/discover/ChatMessageBubble.tsx (add feedback)
```

**Effort:** Low (1 day)

---

## Complete Styling Transformation Guide

### DO's

✅ Use `bg-background` for page backgrounds
✅ Use `bg-card/60 backdrop-blur-md` for elevated surfaces
✅ Use `border-border` or `border-white/10` for borders
✅ Use `text-foreground` and `text-muted-foreground` for text
✅ Use SWE Agent `Button`, `Card`, `Input`, `Badge` components
✅ Use `rounded-xl` for cards, `rounded-md` for inputs
✅ Use `focus-visible:ring-1 focus-visible:ring-ring` for focus states
✅ Use `hover:bg-accent` for hover states

### DON'Ts

❌ Custom gradient backgrounds (`from-[#0b1120] via-[#0f172a]`)
❌ Ambient gradient orbs/blur effects
❌ `text-slate-*` or `text-gray-*` colors
❌ `bg-slate-*` or `bg-gray-*` backgrounds
❌ `border-slate-*` borders
❌ Custom gradient buttons
❌ `rounded-2xl` (use `rounded-xl`)
❌ Cyan/blue accent colors (`text-cyan-400`, `border-cyan-400/40`)

### Component Quick Reference

| Need             | Use                                                         |
| ---------------- | ----------------------------------------------------------- |
| Page background  | `bg-background`                                             |
| Card/panel       | `<Card>` or `bg-card/60 backdrop-blur-md rounded-xl border` |
| Primary button   | `<Button>` (default variant)                                |
| Secondary button | `<Button variant="outline">`                                |
| Ghost button     | `<Button variant="ghost">`                                  |
| Text input       | `<Input>`                                                   |
| Textarea         | `<Textarea>`                                                |
| Status indicator | `<Badge variant="success/warning/destructive/info">`        |
| Section title    | `<CardTitle>` or `text-lg font-semibold`                    |
| Body text        | `text-foreground`                                           |
| Secondary text   | `text-muted-foreground`                                     |
| Hover background | `hover:bg-accent`                                           |
| Focus ring       | `focus-visible:ring-1 focus-visible:ring-ring`              |

---

## Route Structure

```
/discover              - Landing/Search page (DiscoverPage.tsx)
/discover/search?q=    - Active search (ephemeral)
/discover/search?id=   - Saved conversation
/discover/tools        - Tools grid dashboard
/discover/handoff/:id  - Slack handoff
/discover/share/:id    - Shared conversation view
```

### Sidebar Integration

Add to `Sidebar.tsx` navItems:

```typescript
{
  title: 'Discover',
  href: '/discover',
  icon: Telescope,  // or Search, Sparkles
}
```

---

## Implementation Phases

### Phase 1: Core Search (Week 1)

- [ ] Create `/discover` route and navigation
- [ ] Port SearchBar using SWE Agent `Input` and styling
- [ ] Implement streaming service
- [ ] Basic chat message display using `Card` components

### Phase 2: Chat History (Week 1)

- [ ] Port chat history utilities with namespaced keys (`discover-*`)
- [ ] Add ChatSidebar component with SWE Agent styling
- [ ] ChatHistory on landing page
- [ ] Resume conversation functionality

### Phase 3: Rich Results (Week 2)

- [ ] Markdown rendering with citations (use existing react-markdown)
- [ ] CodeRefsPanel and DocLinksPanel using `Card`
- [ ] ThinkingBlock component with disclosure
- [ ] Message styling with `bg-card/60 backdrop-blur-md`

### Phase 4: Settings & Tools (Week 2)

- [ ] Credentials management UI with `Card`, `Button`, `Input`
- [ ] Connection status dashboard with `Badge` variants
- [ ] Tools grid page with category filter buttons
- [ ] Integrate into Settings or create `/discover/settings`

### Phase 5: Polish Features (Week 3)

- [ ] Save/Share functionality
- [ ] Feedback buttons with `Button variant="ghost"`
- [ ] Handoff and Share pages
- [ ] Authentication integration with existing `AuthGuard`

### Phase 6: Testing & Integration (Week 3)

- [ ] End-to-end testing
- [ ] Dark mode verification (primary target)
- [ ] Light mode verification (secondary)
- [ ] Responsive design check
- [ ] Performance optimization

---

## Visual Identity Checklist

Before marking any component complete, verify:

- [ ] No `slate` or `gray` color classes remain
- [ ] No custom gradient backgrounds (except subtle `/20` opacity)
- [ ] No `cyan` accent colors
- [ ] Uses `bg-card/60 backdrop-blur-md` for elevated surfaces
- [ ] Uses `border-border` for borders
- [ ] Uses `text-foreground` / `text-muted-foreground` for text
- [ ] Uses SWE Agent `Button` component (not custom buttons)
- [ ] Uses SWE Agent `Card` component (not custom divs)
- [ ] Uses `rounded-xl` for cards, `rounded-md` for inputs
- [ ] Focus states use `focus-visible:ring-1 focus-visible:ring-ring`
- [ ] Works in dark mode (primary)
- [ ] Works in light mode (secondary)

---

## Appendix: File Mapping

### Discover Files → SWE Agent Location

| Discover File                        | SWE Agent Destination                 |
| ------------------------------------ | ------------------------------------- |
| `App.tsx` routes                     | `App.tsx` route additions             |
| `pages/Landing.tsx`                  | `pages/DiscoverPage.tsx`              |
| `pages/Search.tsx`                   | `pages/DiscoverSearchPage.tsx`        |
| `pages/Settings.tsx`                 | Integrate into existing Settings      |
| `pages/Handoff.tsx`                  | `pages/DiscoverHandoff.tsx`           |
| `pages/Share.tsx`                    | `pages/DiscoverShare.tsx`             |
| `components/landing/SearchBar.tsx`   | `components/discover/SearchBar.tsx`   |
| `components/landing/ChatHistory.tsx` | `components/discover/ChatHistory.tsx` |
| `components/landing/ToolsGrid.tsx`   | `components/discover/ToolsGrid.tsx`   |
| `components/chat/*.tsx`              | `components/discover/chat/*.tsx`      |
| `components/settings/*.tsx`          | `components/settings/Discover*.tsx`   |
| `components/tools/*.tsx`             | `components/discover/tools/*.tsx`     |
| `services/*.service.ts`              | `services/discover-*.service.ts`      |
| `utils/chat-history.ts`              | `utils/discover-chat-history.ts`      |
| `context/AuthContext.tsx`            | Reuse existing auth                   |
| `context/ToolsContext.tsx`           | `context/ToolsContext.tsx`            |
| `types/*.ts`                         | `types/discover.ts` (consolidated)    |

---

## Example: Before & After

### Before (Discover Style)

```tsx
<div className="min-h-screen bg-gradient-to-b from-[#0b1120] via-[#0f172a] to-[#0b1120]">
  <header className="bg-gradient-to-r from-[#0f1a2e]/90 via-[#131f38]/90 to-[#0f1a2e]/90 backdrop-blur-xl border-b border-white/[0.06]">
    <button className="bg-blue-600 hover:bg-blue-500 text-white rounded-xl px-4 py-2">
      Search
    </button>
  </header>
  <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-4">
    <p className="text-slate-100">Content</p>
  </div>
</div>
```

### After (SWE Agent Style)

```tsx
<div className="min-h-screen bg-background">
  <header className="border-b bg-card/60 backdrop-blur-md">
    <Button>Search</Button>
  </header>
  <Card>
    <CardContent>
      <p className="text-foreground">Content</p>
    </CardContent>
  </Card>
</div>
```

---

## Related Documentation

- **[Integration Guide](./discover.md)** - Token exchange architecture and backend configuration
- **[Quick Reference](./discover-quick-ref.md)** - Commands and troubleshooting
- **[UI Integration](./discover-ui-integration.md)** - API proxy and service integration details

---

_Document Version: 1.1 (Visual Identity Aligned)_
_Last Updated: 2026-03-21_
_Migration Lead: [TBD]_
