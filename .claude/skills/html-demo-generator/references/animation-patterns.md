# Animation Patterns

## Core Timer System

Every demo uses a scheduler pattern for sequencing animations:

```javascript
let timeouts = [];
function clearAll() { timeouts.forEach(t => clearTimeout(t)); timeouts = []; }
function sched(fn, d) { timeouts.push(setTimeout(fn, d)); }
```

All animations in `startDemo()` use `sched()` with absolute timestamps from demo start (not relative to previous).

## Scene Transitions

```css
.scene {
  position: absolute;
  inset: 0;          /* or top: 40px for below chrome */
  opacity: 0;
  transition: opacity 0.5s;
  pointer-events: none;
}
.scene.active { opacity: 1; pointer-events: auto; }
```

```javascript
// Switch scenes
document.getElementById('scene1').classList.remove('active');
document.getElementById('scene2').classList.add('active');
```

## Typing Effect

Simulates user typing in a search bar or input field.

```javascript
const searchText = "trino cost";
let typed = '';
for (let c = 0; c < searchText.length; c++) {
  sched(() => {
    typed += searchText[c];
    document.getElementById('search-content').innerHTML =
      '<span class="search-typed">' + typed + '</span>' +
      '<span class="typing-cursor"></span>';
  }, 2200 + c * 80);  // 80ms per character
}
```

```css
.typing-cursor {
  display: inline-block;
  width: 2px;
  height: 14px;
  background: #3B82F6;
  animation: blink 0.8s infinite;
  vertical-align: middle;
  margin-left: 1px;
}
@keyframes blink { 0%,50% { opacity: 1; } 51%,100% { opacity: 0; } }
```

## Element Appear (Fade + Slide Up)

```css
.element {
  opacity: 0;
  transform: translateY(8px);
  transition: all 0.4s ease;
}
.element.visible {
  opacity: 1;
  transform: translateY(0);
}
```

```javascript
// Stagger card appearances (150ms between each)
for (let i = 1; i <= 6; i++) {
  sched(() => document.getElementById('card'+i).classList.add('visible'), 300 + i * 150);
}
```

## Streaming Log Lines

```html
<div class="exec-log">
  <div class="log-line" id="log1">
    <span class="log-ts">[09:00:01]</span>
    <span class="log-info">Starting task...</span>
  </div>
  <!-- more lines -->
</div>
```

```css
.exec-log {
  background: rgba(15,23,42,0.8);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  line-height: 1.7;
  height: 180px;
  overflow: hidden;
}
.log-line { opacity: 0; transform: translateY(4px); transition: all 0.3s; }
.log-line.visible { opacity: 1; transform: translateY(0); }
.log-ts { color: #475569; }
.log-info { color: #3B82F6; }
.log-success { color: #22C55E; }
.log-mcp { color: #06B6D4; }
.log-warn { color: #EF4444; }
```

```javascript
const logTimings = [9200, 9800, 10600, 11200, 12000, 12800, 13400, 14200];
logTimings.forEach((t, i) => {
  sched(() => document.getElementById('log'+(i+1)).classList.add('visible'), t);
});
```

## Progress Bar

```html
<div class="progress-bar">
  <div class="progress-fill" id="progress-fill"></div>
</div>
```

```css
.progress-bar {
  height: 6px;
  background: rgba(51,65,85,0.5);
  border-radius: 3px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #A855F7, #3B82F6);
  border-radius: 3px;
  transition: width 0.8s ease;
  width: 0%;
}
```

```javascript
// Sync with log lines
const progressSteps = [8, 20, 40, 55, 72, 85, 95, 100];
logTimings.forEach((t, i) => {
  sched(() => {
    document.getElementById('progress-fill').style.width = progressSteps[i] + '%';
    document.getElementById('progress-pct').textContent = progressSteps[i] + '%';
  }, t);
});
```

## Status Badge Transition

```javascript
// Running → Completed
sched(() => {
  const badge = document.getElementById('status');
  badge.className = 'status-badge status-completed';
  badge.innerHTML = '✅ Completed';
}, 14600);
```

## Slack Message Appear

```css
.slack-card {
  background: rgba(54,197,240,0.06);
  border: 1px solid rgba(54,197,240,0.15);
  border-radius: 10px;
  padding: 12px 14px;
  display: flex;
  gap: 10px;
  opacity: 0;
  transform: translateY(8px);
  transition: all 0.5s ease;
}
.slack-card.visible { opacity: 1; transform: translateY(0); }
```

## Button Click Effect

```css
.btn.clicked { transform: scale(0.95); opacity: 0.8; }
```

```javascript
sched(() => document.getElementById('btn').classList.add('clicked'), 7500);
```

## Pulse/Glow Highlight

```css
.highlight {
  border-color: rgba(168,85,247,0.4);
  box-shadow: 0 0 20px rgba(168,85,247,0.08);
}
.pulse-highlight {
  animation: btnPulse 1s ease 2;
}
@keyframes btnPulse {
  0%,100% { box-shadow: none; }
  50% { box-shadow: 0 0 12px rgba(59,130,246,0.2); }
}
```

## Grid Filter (Hide/Show Cards)

When filtering a grid, use `display: none` after fade to avoid layout gaps:

```javascript
['card2','card4'].forEach(id => {
  const el = document.getElementById(id);
  el.style.transition = 'opacity 0.3s';
  el.style.opacity = '0';
  setTimeout(() => { el.style.display = 'none'; }, 300);
});
```

## SVG Animated Data Packets (Flow Diagrams)

For connection lines between nodes:

```html
<svg class="connections" viewBox="0 0 900 520">
  <line x1="450" y1="260" x2="200" y2="100" stroke="rgba(59,130,246,0.3)" stroke-width="2" stroke-dasharray="6,4"/>
  <circle class="packet" r="4" fill="#3B82F6">
    <animateMotion dur="2s" repeatCount="indefinite" path="M450,260 L200,100"/>
  </circle>
</svg>
```

## Auto-Loop and Replay

```javascript
// At the end of startDemo():
sched(() => document.getElementById('replay-btn').classList.add('visible'), 16500);
sched(() => startDemo(), 20000);  // Auto-restart after 3-5s pause
```

## Timing Cheat Sheet

| Animation | Duration | Stagger |
|-----------|----------|---------|
| Card appear | 400ms | 150ms between cards |
| Scene fade | 500ms | — |
| Typing | 60-100ms/char | — |
| Log line appear | 300ms | 600-800ms between lines |
| Progress bar | 800ms ease | synced with logs |
| Slack notification | 500ms | — |
| Hold final state | 2-3s | — |
| Auto-loop delay | 3-5s | — |
| Full demo cycle | 15-25s total | — |
