# Design Tokens

## Kriya Theme (Default)

Use for any demo showcasing Kriya platform features (Autonomous Agent, Skills, Event Listener, etc.)

```css
:root {
  --bg: #0F172A;
  --card: rgba(15,23,42,0.6);
  --border: rgba(51,65,85,0.6);
  --text: #E2E8F0;
  --muted: #94A3B8;
  --blue: #3B82F6;
  --cyan: #06B6D4;
  --green: #22C55E;
  --purple: #A855F7;
  --yellow: #EAB308;
  --red: #EF4444;
}
```

### Sidebar

```css
.sidebar {
  width: 200px;
  border-right: 1px solid var(--border);
  padding: 16px 10px;
  flex-shrink: 0;
}
.logo { font-size: 15px; font-weight: 700; margin-bottom: 20px; padding: 0 6px; }
.logo span { background: linear-gradient(135deg, #3B82F6, #06B6D4); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.nav-item { padding: 8px 10px; border-radius: 8px; font-size: 13px; color: var(--muted); display: flex; align-items: center; gap: 8px; margin-bottom: 2px; }
.nav-item.active { background: rgba(59,130,246,0.15); color: var(--text); }
```

### Sidebar Nav Items (Standard)

```html
<div class="logo">Razorpay <span>Kriya</span></div>
<div class="nav-item"><span class="nav-icon">🏠</span> Home</div>
<div class="nav-item"><span class="nav-icon">🤖</span> Autonomous Agent</div>
<div class="nav-item"><span class="nav-icon">📦</span> Agents Catalogue</div>
<div class="nav-item active"><span class="nav-icon">✨</span> Skills Catalogue</div>
<div class="nav-item"><span class="nav-icon">📋</span> Tasks</div>
<div class="nav-item"><span class="nav-icon">⚡</span> MCP Gateway</div>
<div class="nav-item"><span class="nav-icon">👥</span> Team</div>
```

### Glass Cards

```css
.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px;
  backdrop-filter: blur(12px);
}
```

### Status Badges

```css
.status-badge {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 600;
}
.status-running { background: rgba(59,130,246,0.15); color: var(--blue); border: 1px solid rgba(59,130,246,0.3); }
.status-completed { background: rgba(34,197,94,0.15); color: var(--green); border: 1px solid rgba(34,197,94,0.3); }
.status-queued { background: rgba(234,179,8,0.15); color: var(--yellow); border: 1px solid rgba(234,179,8,0.3); }
.status-failed { background: rgba(239,68,68,0.15); color: var(--red); border: 1px solid rgba(239,68,68,0.3); }
```

### Buttons

```css
.btn-primary {
  padding: 6px 14px;
  border-radius: 6px;
  background: rgba(168,85,247,0.15);
  border: 1px solid rgba(168,85,247,0.25);
  color: #A855F7;
  font-size: 11px;
  font-weight: 600;
}
.btn-secondary {
  padding: 6px 14px;
  border-radius: 6px;
  background: transparent;
  border: 1px solid var(--border);
  color: var(--muted);
  font-size: 11px;
  font-weight: 600;
}
```

---

## GitHub Theme

Use for demos showing GitHub UI (code review, PR diffs, etc.)

```css
:root {
  --bg-dark: #0D1117;
  --bg-card: #161B22;
  --bg-diff: #1C2128;
  --border: rgba(48, 54, 61, 0.8);
  --text-primary: #E6EDF3;
  --text-muted: #8B949E;
  --blue: #58A6FF;
  --green: #3FB950;
  --red: #F85149;
  --yellow: #D29922;
  --orange: #F0883E;
  --purple: #BC8CFF;
  --diff-add-bg: rgba(63, 185, 80, 0.15);
  --diff-del-bg: rgba(248, 81, 73, 0.15);
}
```

---

## Slack Theme

Use for demos showing Slack messages, threads, channels.

```css
:root {
  --slack-bg: #1A1D21;
  --slack-sidebar: #19171D;
  --slack-hover: rgba(255,255,255,0.04);
  --slack-text: #D1D2D3;
  --slack-muted: #ABABAD;
  --slack-link: #1D9BD1;
  --slack-border: rgba(255,255,255,0.08);
  --slack-active-channel: rgba(29,155,209,0.12);
}
```

### Slack Message Component

```css
.slack-msg { display: flex; gap: 10px; padding: 6px 20px; }
.slack-avatar { width: 36px; height: 36px; border-radius: 6px; flex-shrink: 0; }
.slack-author { font-weight: 700; font-size: 15px; color: var(--slack-text); }
.slack-badge { font-size: 10px; background: rgba(29,155,209,0.15); color: #1D9BD1; padding: 1px 6px; border-radius: 3px; font-weight: 600; }
.slack-time { font-size: 11px; color: var(--slack-muted); }
.slack-text { font-size: 14px; color: var(--slack-text); line-height: 1.5; }
```

---

## DevRev Theme

Use for demos showing DevRev tickets, events, timeline.

```css
:root {
  --devrev-bg: #0F172A;
  --devrev-card: rgba(15,23,42,0.8);
  --devrev-border: rgba(51,65,85,0.5);
  --devrev-text: #E2E8F0;
  --devrev-muted: #94A3B8;
  --devrev-purple: #8B5CF6;
  --devrev-blue: #3B82F6;
}
```

---

## Container Structure

```css
.demo-container {
  width: 900px;
  height: 560px;
  border-radius: 16px;
  border: 1px solid var(--border);
  background: var(--card);
  backdrop-filter: blur(12px);
  overflow: hidden;
  position: relative;
  box-shadow: 0 25px 60px rgba(0,0,0,0.5);
}

.window-chrome {
  height: 40px;
  background: rgba(30, 41, 59, 0.8);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 0 16px;
  gap: 8px;
}
.dot { width: 12px; height: 12px; border-radius: 50%; }
.dot-red { background: #EF4444; }
.dot-yellow { background: #EAB308; }
.dot-green { background: #22C55E; }
```

### Replay Button

```css
.replay-btn {
  position: absolute; bottom: 12px; right: 12px;
  background: rgba(168,85,247,0.12);
  border: 1px solid rgba(168,85,247,0.25);
  color: #A855F7;
  padding: 5px 12px; border-radius: 6px;
  font-size: 11px; font-weight: 600;
  cursor: pointer; z-index: 100;
  opacity: 0; transition: all 0.3s;
  font-family: 'Inter', sans-serif;
}
.replay-btn.visible { opacity: 1; }
```

---

## Typography

- Primary font: `'Inter', -apple-system, BlinkMacSystemFont, sans-serif`
- Code/mono font: `'JetBrains Mono', monospace`
- Import: `@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;900&family=JetBrains+Mono:wght@400;500&display=swap');`
