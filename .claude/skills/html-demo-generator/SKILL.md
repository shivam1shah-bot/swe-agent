---
name: html-demo-generator
description: Generates self-contained animated HTML demo files from product UI screenshots, Slack messages, or live app pages. Creates looping, scene-based animations that showcase product features — typing effects, streaming logs, progress bars, scene transitions. Use when asked to create a demo, demo image, animated mockup, or product showcase for a feature. Triggers on "create a demo", "demo for this feature", "animated mockup", "product demo html".
---

# HTML Demo Generator

Generate self-contained, single-file HTML demos that showcase product features through animated scenes. Each demo is a looping animation — no user interaction required — designed to be embedded in a product website or shared standalone.

## When to Use

- User asks to create a demo, animated mockup, or product showcase
- User shares a screenshot or URL and wants an animated version
- User wants a demo image/video replacement for a website section

## Workflow

### Step 1 — Gather Context

Before writing any code, gather the real content for the demo:

1. **If a URL is provided**: Navigate to the page using Chrome tools, take screenshots, extract page text. Capture actual UI content — labels, data, layout.
2. **If a screenshot is provided**: Read the image to understand the UI being demoed.
3. **If Slack links are provided**: Read the Slack messages to capture real bot output, ticket IDs, channel names, usernames.
4. **If existing demos exist**: Read them to match the established visual style and patterns. Check the output directory for prior demos.

Always use real data (ticket IDs, repo names, channel names, usernames) — never placeholder text.

### Step 2 — Decide Demo Type

| Type | When to use | Example |
|------|-------------|---------|
| **App UI Mockup** | Demoing a product screen with interactions | Autonomous Agent, Skills Catalogue |
| **Flow Diagram** | Showing system connections or data flow | MCP Gateway |
| **Split Panel** | Showing cause-and-effect (event → action) | Event Listener |
| **Chat/Thread** | Demoing messaging or bot interactions | Slack Integration |

### Step 3 — Build the Demo

Create a single self-contained HTML file. All CSS and JS inline — no external dependencies except Google Fonts.

#### Required Structure

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>[Feature Name] Demo</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;900&family=JetBrains+Mono:wght@400;500&display=swap');
  /* All styles inline */
</style>
</head>
<body>
<div class="demo-container">
  <div class="window-chrome">
    <div class="dot dot-red"></div>
    <div class="dot dot-yellow"></div>
    <div class="dot dot-green"></div>
  </div>
  <!-- Demo content here -->
</div>
<button class="replay-btn" id="replay-btn" onclick="startDemo()">↻ Replay</button>
<script>
let timeouts = [];
function clearAll() { timeouts.forEach(t => clearTimeout(t)); timeouts = []; }
function sched(fn, d) { timeouts.push(setTimeout(fn, d)); }

function resetAll() { /* Reset all elements to initial state */ }
function startDemo() { resetAll(); /* Schedule all animations */ }
startDemo();
</script>
</body>
</html>
```

#### Design System

Reference `references/design-tokens.md` for the complete token set. Key values:

**Kriya theme (default):** Background `#0F172A`, card `rgba(15,23,42,0.6)`, border `rgba(51,65,85,0.6)`, text `#E2E8F0`, muted `#94A3B8`. Brand colors: blue `#3B82F6`, cyan `#06B6D4`, green `#22C55E`, purple `#A855F7`.

**GitHub theme:** Background `#0D1117`, card `#161B22`, text `#E6EDF3`, muted `#8B949E`.

**Slack theme:** Background `#1A1D21`, sidebar `#19171D`, text `#D1D2D3`.

#### Container Sizing

- Demo container: `900px × 560px`, `border-radius: 16px`
- Window chrome: `40px` height with red/yellow/green dots
- No URL bar — just the three dots
- Sidebar: `200px` width (for app UI mockups)

#### Animation Patterns

Reference `references/animation-patterns.md` for detailed code. Core patterns:

**Scene system:** Use absolute-positioned `.scene` divs. Toggle `.active` class for transitions with `opacity` and `transition: opacity 0.5s`.

**Typing effect:** Build character-by-character with `sched()` calls at 60-100ms intervals. Show a blinking cursor span.

**Streaming logs:** Lines appear one at a time with `opacity` and `translateY` transitions. Use JetBrains Mono font, timestamp prefix in dim color.

**Progress bar:** Animate `width` percentage with `transition: width 0.8s ease`.

**Card/element appear:** Use `opacity: 0` + `translateY(8px)` as initial state, toggle to visible with class.

**Auto-loop:** Schedule `startDemo()` call 3-5 seconds after the last animation completes.

#### Timing Guidelines

- Cards/elements appearing: 150ms stagger between items
- Typing speed: 60-100ms per character
- Scene transitions: 500ms fade
- Hold time on completed state: 2-3 seconds before next scene
- Full demo loop: 15-25 seconds total
- Auto-restart delay: 3-5 seconds after final scene

### Step 4 — Validate and Deliver

1. Save the HTML file to the output directory
2. If a specific deployment path is known (e.g., `ui/public/demos/`), copy there too
3. Share the file link to the user

## Common Pitfalls

- **Don't use `opacity: 0` to hide grid items** — they still take space. Use `display: none` after fade-out for grid reflow.
- **Don't use placeholder data** — always use real ticket IDs, repo names, channel names from Slack/DevRev context.
- **Don't add a URL bar** — just the three window dots.
- **Don't use `localhost` URLs** — use the production/stage domain.
- **Don't show the UI screenshot as-is** for system/architecture demos — create creative flow diagrams instead.
- **Don't exceed 560px height** — the demo must fit without scrolling.
- **Always include a replay button** — positioned at bottom-right, appears after demo completes.
- **Always auto-loop** — demos run continuously without user interaction.
