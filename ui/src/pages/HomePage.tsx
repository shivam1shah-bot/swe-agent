import {
  Bot,
  ArrowRight,
  GitPullRequest,
  Clock,
  MessageSquare,
  CheckCircle2,
  Hammer,
  PlayCircle,
  Sparkles,
  Zap,
  Telescope,
} from 'lucide-react'

// ─── Feature deep-dives ───────────────────────────────────────────────────────

interface LiveFeature {
  id: string
  title: string
  tagline: string
  description: string
  icon: React.ComponentType<{ className?: string }>
  iconColor: string
  iconBg: string
  bullets: string[]
  demoHref?: string
  demoLabel?: string
  /** Path to iframe demo HTML file, if available */
  demoSrc?: string
  imageAlt: string
}

const liveFeatures: LiveFeature[] = [
  {
    id: 'autonomous-agent',
    title: 'Autonomous Coding Agent',
    tagline: 'Ship code while you sleep',
    description:
      'Give Vyom a task in plain English. It clones the repo, writes code, runs tests, opens a PR — and posts an update on Slack. No hand-holding required.',
    icon: Bot,
    iconColor: 'text-blue-500',
    iconBg: 'bg-blue-500/10',
    bullets: [
      'Works on Razorpay private repos',
      'Batch mode — run the same task across many repos at once',
      'Multi-repo mode — orchestrate tasks spanning multiple repos',
      'Clean-slate mode — no repo needed, works with skills directly',
      'Full streaming execution logs',
    ],
    demoLabel: 'Try Autonomous Agent',
    demoHref: '/autonomous-agent',
    demoSrc: '/demos/autonomous-agent.html',
    imageAlt: 'Autonomous agent running a task on a repo',
  },
  {
    id: 'skills',
    title: 'Skills & Schedules',
    tagline: 'Automate the boring stuff, forever',
    description:
      'Skills are composable AI tasks — generate a standup, create a Slack digest, analyse PR metrics. Run them now or schedule them to repeat on a cron.',
    icon: Sparkles,
    iconColor: 'text-violet-500',
    iconBg: 'bg-violet-500/10',
    bullets: [
      'One-off or recurring via cron expression',
      'Growing library of built-in skills',
      'Trigger via UI or REST API',
      'Results posted to Slack or stored as tasks',
    ],
    demoLabel: 'Browse Skills',
    demoHref: '/skills-catalogue',
    demoSrc: '/demos/skills-schedules.html',
    imageAlt: 'Skills catalogue with schedule modal',
  },
  {
    id: 'slack',
    title: 'Slack Integration',
    tagline: 'Your AI team member, right in Slack',
    description:
      'Vyom posts summaries, digests, and PR reviews directly to Slack. Trigger agents from a message. Get notified when tasks complete.',
    icon: MessageSquare,
    iconColor: 'text-yellow-500',
    iconBg: 'bg-yellow-500/10',
    bullets: [
      'AI-generated channel digests & standups',
      'Cross-channel topic search',
      'Task completion notifications',
      'Announcement drafting assistant',
      'Trigger agents directly from Slack with a DevRev ticket',
    ],
    demoSrc: '/demos/slack-integration.html',
    imageAlt: 'Slack digest message from Vyom bot',
  },
  {
    id: 'event-listener',
    title: 'Vyom Event Listener',
    tagline: 'Zero-touch task pickup',
    description:
      'Vyom watches DevRev for tickets assigned to it and triggers the right agent automatically — no manual intervention needed.',
    icon: Zap,
    iconColor: 'text-emerald-500',
    iconBg: 'bg-emerald-500/10',
    bullets: [
      'Auto-picks tickets based on configurable criteria',
      'Routes to the right agent based on ticket context',
      'Posts progress and results back on the DevRev thread',
    ],
    demoSrc: '/demos/event-listener.html',
    imageAlt: 'Vyom event listener picking a DevRev ticket',
  },
  {
    id: 'mcp',
    title: 'MCP Gateway',
    tagline: 'Every tool, one agent',
    description:
      'Agents connect to external systems via Model Context Protocol — Slack, DevRev, Grafana, and more — without writing any integration code.',
    icon: Zap,
    iconColor: 'text-purple-500',
    iconBg: 'bg-purple-500/10',
    bullets: [
      'Slack — post, search, and summarise channels',
      'DevRev — tickets, issues, incidents, and customer support',
      'Grafana — log monitoring and observability',
      'Blade MCP — Razorpay design system integration',
      'Memory — persistent context across agent runs',
    ],
    demoLabel: 'Explore MCP Gateway',
    demoHref: '/mcp-gateway',
    demoSrc: '/demos/mcp-gateway.html',
    imageAlt: 'MCP gateway server list with tool count',
  },
  {
    id: 'user-mapping',
    title: 'Persisted User Mapping & Task Filtering',
    tagline: 'Every task traced to its owner',
    description:
      'User identities are automatically mapped across Slack, Dashboard, and DevRev — so every task is attributed correctly. Filter the task list by user, email, or connector source to see exactly what matters to you.',
    icon: CheckCircle2,
    iconColor: 'text-violet-500',
    iconBg: 'bg-violet-500/10',
    bullets: [
      'One user_connector record per engineer, merged across all connectors',
      'Each task records which connector triggered it (Slack, Dashboard, DevRev)',
      'Filter tasks by connector source or user email dropdown',
      '"My Tasks" toggle shows only your tasks instantly',
      'User identity visible in the Triggered By column with connector badge',
    ],
    demoSrc: '/demos/user-mapping.html',
    imageAlt: 'Tasks page with user filter dropdown and connector badges',
  },
  {
    id: 'pr-review',
    title: 'rCoRe — Razorpay Code Review',
    tagline: 'Every PR reviewed before a human even opens it',
    description:
      'rCoRe runs a fleet of specialised sub-agents on every pull request — each expert in a different dimension of code quality — then synthesises findings into inline GitHub comments.',
    icon: GitPullRequest,
    iconColor: 'text-orange-500',
    iconBg: 'bg-orange-500/10',
    bullets: [
      'Parallel sub-agents: bug detection, security, code quality, Blade, i18n, pre-mortem',
      'Clones the repo and reads actual file context — not just the diff',
      'Uses repo-specific code-review skills for standards-aware severity scoring',
      'AI filter layer removes false positives before any comment is posted',
      'Auto-approves low-severity PRs with zero human intervention',
    ],
    demoSrc: '/demos/rcore-review.html',
    imageAlt: 'rCoRe inline review comments on a GitHub PR',
  },
  {
    id: 'ai-hub',
    title: 'AI Stack Dashboard',
    tagline: 'Complete AI tools catalog',
    description:
      'Comprehensive dashboard showing all AI tools, plugins, MCPs, and skills across the Razorpay engineering organization. Browse by SDLC stage, check production readiness, and find capabilities and gaps for each tool.',
    icon: Telescope,
    iconColor: 'text-violet-500',
    iconBg: 'bg-violet-500/10',
    bullets: [
      'Browse 25+ AI tools organized by SDLC stage (Planning to Production)',
      'View production readiness status (GA, Preview, In Development)',
      'See what each tool can and cannot do with detailed capability listings',
      'Filter by type: Plugins, MCPs, Skills, and Agents',
      'Quick links to documentation, Slack channels, and POC contacts',
    ],
    demoLabel: 'View AI Stack',
    demoHref: '/ai-hub',
    imageAlt: 'AI Stack Dashboard showing tools by stage',
  },
]

// ─── Coming soon ──────────────────────────────────────────────────────────────

const comingFeatures = [
  {
    title: 'Agent Task Resume',
    description: 'GitHub PRs, Slack messages, and other DevRev-connected events flow back into the ticket — automatically resuming the agent session with full context whenever something relevant happens.',
    icon: Bot,
    iconColor: 'text-blue-500',
    eta: '',
  },
  {
    title: 'Scheduled Trigger of Skills & Agents',
    description: 'Run any skill or agent on a cron schedule — standups, audits, sweeps — without any manual trigger.',
    icon: Clock,
    iconColor: 'text-orange-500',
    eta: '',
  },
  {
    title: 'Agent Observability',
    description: 'Deep visibility into agent runs — traces, tool calls, latency, errors — so you can understand and improve what agents are doing.',
    icon: GitPullRequest,
    iconColor: 'text-emerald-500',
    eta: '',
  },
  {
    title: 'Broader Internal Tool Connectivity',
    description: 'Expanding Vyom\'s reach across the Razorpay ecosystem — infra tools, Devstack, quality, security, and more — so agents can act across the entire engineering stack.',
    icon: Zap,
    iconColor: 'text-blue-500',
    eta: '',
  },
  {
    title: 'Agent Catalogue v2',
    description: 'A unified catalogue of all agents from the claude-plugins repo — browse, execute, and schedule any agent directly from the UI without any setup.',
    icon: Sparkles,
    iconColor: 'text-emerald-500',
    eta: '',
  },
]

// ─── Scaled iframe demo ───────────────────────────────────────────────────────

function ScaledIframeDemo({ src, title }: { src: string; title: string }) {
  return (
    <div
      className="w-full rounded-2xl border border-white/10 overflow-hidden"
      style={{ aspectRatio: '900/560', position: 'relative' }}
    >
      <iframe
        src={src}
        title={title}
        scrolling="no"
        style={{
          border: 'none',
          position: 'absolute',
          top: 0,
          left: 0,
          width: '900px',
          height: '560px',
          transformOrigin: 'top left',
        }}
        ref={(el) => {
          if (!el) return
          const resize = () => {
            const scale = el.parentElement!.clientWidth / 900
            el.style.transform = `scale(${scale})`
            el.parentElement!.style.height = `${560 * scale}px`
          }
          resize()
          const ro = new ResizeObserver(resize)
          ro.observe(el.parentElement!)
        }}
      />
    </div>
  )
}

// ─── Demo image placeholder ───────────────────────────────────────────────────

function DemoImagePlaceholder({ alt, index }: { alt: string; index: number }) {
  const gradients = [
    'from-blue-500/20 via-cyan-500/10 to-blue-500/5',
    'from-orange-500/20 via-rose-500/10 to-orange-500/5',
    'from-violet-500/20 via-purple-500/10 to-violet-500/5',
    'from-purple-500/20 via-fuchsia-500/10 to-purple-500/5',
    'from-yellow-500/20 via-amber-500/10 to-yellow-500/5',
  ]
  return (
    <div
      className={`w-full rounded-2xl border border-white/10 bg-gradient-to-br ${gradients[index % gradients.length]} relative overflow-hidden`}
      style={{ aspectRatio: '16/9' }}
      aria-label={alt}
    >
      <div className="absolute inset-0 flex flex-col">
        <div className="flex items-center gap-1.5 px-4 py-3 border-b border-white/10">
          <div className="h-2.5 w-2.5 rounded-full bg-red-400/60" />
          <div className="h-2.5 w-2.5 rounded-full bg-yellow-400/60" />
          <div className="h-2.5 w-2.5 rounded-full bg-green-400/60" />
          <div className="ml-4 h-2 w-40 rounded-full bg-white/10" />
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-2 opacity-40">
            <PlayCircle className="h-10 w-10 mx-auto text-white" />
            <p className="text-xs text-white font-medium">Demo coming soon</p>
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function HomePage() {
  return (
    <div className="flex-1 p-8 relative min-h-screen">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-100 via-transparent to-transparent opacity-50 dark:from-slate-800/40 dark:via-background dark:to-background pointer-events-none -z-10" />

      <div className="relative z-10 max-w-5xl mx-auto space-y-16">

        {/* ── Header ── */}
        <div className="mt-2 space-y-4">
          <div>
            <h1 className="text-4xl font-bold tracking-tight text-slate-900 dark:text-white">
              Welcome to{' '}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-cyan-500">
                Vyom
              </span>
            </h1>
            <p className="text-muted-foreground mt-2 text-base">Cloud Agents for Razorpay</p>
          </div>

        </div>


        {/* ── Feature deep-dives ── */}
        <div className="space-y-6">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-sm font-semibold text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="h-4 w-4" />
              Live now
            </div>
            <div className="flex-1 h-px bg-border" />
          </div>

          <div className="space-y-20">
            {liveFeatures.map((feature, i) => (
              <div
                key={feature.id}
                className={`flex flex-col ${i % 2 === 0 ? 'lg:flex-row' : 'lg:flex-row-reverse'} gap-10 lg:gap-16 items-center`}
              >
                <div className="flex-1 space-y-5 min-w-0">
                  <div className={`inline-flex items-center justify-center w-11 h-11 rounded-xl ${feature.iconBg}`}>
                    <feature.icon className={`h-5 w-5 ${feature.iconColor}`} />
                  </div>
                  <div className="space-y-1">
                    <p className={`text-xs font-semibold uppercase tracking-widest ${feature.iconColor}`}>
                      {feature.tagline}
                    </p>
                    <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
                      {feature.title}
                    </h2>
                  </div>
                  <p className="text-muted-foreground leading-relaxed">{feature.description}</p>
                  <ul className="space-y-2.5">
                    {feature.bullets.map((b) => (
                      <li key={b} className="flex items-start gap-2.5 text-sm text-slate-700 dark:text-slate-300">
                        <CheckCircle2 className={`h-4 w-4 shrink-0 mt-0.5 ${feature.iconColor}`} />
                        {b}
                      </li>
                    ))}
                  </ul>
                  {feature.demoHref && (
                    <a
                      href={feature.demoHref}
                      className={`inline-flex items-center gap-2 text-sm font-semibold ${feature.iconColor} hover:opacity-80 transition-opacity`}
                    >
                      {feature.demoLabel}
                      <ArrowRight className="h-4 w-4" />
                    </a>
                  )}
                </div>
                <div className="flex-1 w-full min-w-0">
                  {feature.demoSrc ? (
                    <ScaledIframeDemo src={feature.demoSrc} title={feature.imageAlt} />
                  ) : (
                    <DemoImagePlaceholder alt={feature.imageAlt} index={i} />
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ── Coming soon ── */}
        <div className="space-y-6">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-sm font-semibold text-amber-600 dark:text-amber-400">
              <Hammer className="h-4 w-4" />
              In the works
            </div>
            <div className="flex-1 h-px bg-border" />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {comingFeatures.map((f) => (
              <div
                key={f.title}
                className="rounded-2xl border bg-card/40 backdrop-blur-sm p-5 space-y-3 hover:bg-card/60 transition-colors"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="inline-flex items-center justify-center w-9 h-9 rounded-xl bg-slate-100 dark:bg-slate-800">
                    <f.icon className={`h-4 w-4 ${f.iconColor}`} />
                  </div>
                  {f.eta && (
                    <span className="text-xs font-medium text-muted-foreground bg-muted px-2.5 py-1 rounded-full">
                      {f.eta}
                    </span>
                  )}
                </div>
                <div>
                  <h3 className="font-semibold text-sm text-slate-900 dark:text-white">{f.title}</h3>
                  <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{f.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ── Footer ── */}
        <div className="text-center space-y-4 py-4 pb-12">
          <p className="text-muted-foreground text-sm">Want to request a feature or report an issue?</p>
          <a
            href="https://github.com/razorpay/swe-agent/issues"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-slate-900 dark:bg-white text-white dark:text-slate-900 text-sm font-semibold hover:opacity-90 transition-opacity"
          >
            Open a GitHub issue
            <ArrowRight className="h-4 w-4" />
          </a>
        </div>

      </div>
    </div>
  )
}
