import { useState, useEffect, useRef, useCallback } from 'react'
import { Puzzle, Search, X, ExternalLink, ChevronDown, ChevronRight, Loader2, Bot, RefreshCw } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent } from '@/components/ui/dialog'
import { apiClient, Plugin, PluginAgent } from '@/lib/api'

const formatName = (name: string) =>
  name.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())

// ── stat pills ────────────────────────────────────────────────────────────────

function StatPill({ count, label, color }: { count: number; label: string; color: string }) {
  if (!count) return null
  return (
    <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${color}`}>
      <span className="font-bold">{count}</span> {label}
    </span>
  )
}

function BoolPill({ active, label }: { active: boolean; label: string }) {
  if (!active) return null
  return (
    <span className="inline-flex items-center text-xs px-2 py-0.5 rounded-full font-medium bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
      {label}
    </span>
  )
}

// ── fetch hook ────────────────────────────────────────────────────────────────

function usePluginAgents(pluginDir: string, hasAgents: boolean) {
  const [data, setData]       = useState<PluginAgent[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState<string | null>(null)
  const fetchedRef = useRef(false)

  const fetch = useCallback(() => {
    if (!hasAgents) return
    fetchedRef.current = true
    setLoading(true)
    setError(null)
    apiClient.getPluginAgents(pluginDir)
      .then(d => setData(d))
      .catch(e => {
        setError(e instanceof Error ? e.message : String(e))
        fetchedRef.current = false
      })
      .finally(() => setLoading(false))
  }, [pluginDir, hasAgents])

  useEffect(() => {
    if (!fetchedRef.current) fetch()
  }, [fetch])

  return { data, loading, error, retry: fetch }
}

// ── agent row ─────────────────────────────────────────────────────────────────

const FIELD_LABELS: Record<string, string> = {
  tools: 'Tools', disallowedTools: 'Disallowed tools', model: 'Model',
  permissionMode: 'Permission', maxTurns: 'Max turns', skills: 'Skills',
  mcpServers: 'MCP servers', hooks: 'Hooks', memory: 'Memory',
  background: 'Background', isolation: 'Isolation',
}

function AgentRow({ agent }: { agent: PluginAgent }) {
  const [open, setOpen] = useState(false)
  const hasFields = Object.keys(agent.fields).length > 0

  return (
    <div className="rounded-lg border border-slate-200 dark:border-slate-800 overflow-hidden">
      <button
        className="w-full flex items-center gap-2 px-3 py-2.5 bg-slate-50 dark:bg-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors text-left"
        onClick={() => setOpen(o => !o)}
      >
        <Bot className="h-3.5 w-3.5 text-violet-400 shrink-0" />
        <span className="text-xs font-medium text-slate-800 dark:text-slate-200 flex-1 truncate">
          {formatName(agent.name)}
        </span>
        {open
          ? <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          : <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />}
      </button>

      {open && (
        <div className="border-t border-slate-200 dark:border-slate-800 px-3 py-3 bg-white dark:bg-slate-950 space-y-2.5">
          {agent.description && (
            <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
              {agent.description}
            </p>
          )}
          {hasFields && (
            <dl className="space-y-1 pt-1 border-t border-slate-100 dark:border-slate-800">
              {Object.entries(agent.fields).map(([key, val]) => (
                <div key={key} className="flex gap-2 text-xs">
                  <dt className="text-muted-foreground shrink-0 w-28">
                    {FIELD_LABELS[key] ?? key}
                  </dt>
                  <dd className="text-slate-700 dark:text-slate-300 font-mono break-all">
                    {Array.isArray(val) ? val.join(', ') : val}
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      )}
    </div>
  )
}

// ── card ──────────────────────────────────────────────────────────────────────

function PluginCard({ plugin, onClick }: { plugin: Plugin; onClick: () => void }) {
  const tags = (plugin.keywords ?? []).slice(0, 3)

  return (
    <Card className="flex flex-col hover:shadow-md transition-shadow cursor-pointer" onClick={onClick}>
      <CardContent className="p-5 flex flex-col gap-3 flex-1">
        <div className="flex items-center gap-2 min-w-0">
          <div className="h-8 w-8 rounded-lg bg-violet-100 dark:bg-violet-950 flex items-center justify-center shrink-0">
            <Puzzle className="h-4 w-4 text-violet-600 dark:text-violet-400" />
          </div>
          <h3 className="font-semibold text-sm leading-tight truncate">{formatName(plugin.name)}</h3>
        </div>

        <p className="text-xs text-muted-foreground line-clamp-2 flex-1">
          {plugin.description || 'No description available.'}
        </p>

        <div className="flex flex-wrap gap-1.5">
          <StatPill count={plugin.agent_count}   label="agents"   color="bg-violet-100 text-violet-700 dark:bg-violet-950 dark:text-violet-300" />
          <StatPill count={plugin.skill_count}   label="skills"   color="bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300" />
          <StatPill count={plugin.command_count} label="commands" color="bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300" />
          <BoolPill active={plugin.has_hooks} label="hooks" />
          <BoolPill active={plugin.has_mcp}   label="MCP" />
          <BoolPill active={plugin.has_lsp}   label="LSP" />
        </div>

        {tags.length > 0 && (
          <div className="flex flex-wrap gap-1 pt-0.5">
            {tags.map(tag => (
              <span key={tag} className="text-xs bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 px-1.5 py-0.5 rounded">
                {tag}
              </span>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ── drawer ────────────────────────────────────────────────────────────────────

function PluginDrawer({ plugin, onClose }: { plugin: Plugin; onClose: () => void }) {
  const [agentsExpanded, setAgentsExpanded] = useState(true)
  const { data: agentData, loading: agentLoading, error: agentError, retry } =
    usePluginAgents(plugin.plugin_dir, plugin.agents.length > 0)

  return (
    <Dialog open onOpenChange={open => !open && onClose()}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto p-0">
        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b">
          <div className="flex items-start gap-3 min-w-0">
            <div className="h-10 w-10 rounded-xl bg-violet-100 dark:bg-violet-950 flex items-center justify-center shrink-0 mt-0.5">
              <Puzzle className="h-5 w-5 text-violet-600 dark:text-violet-400" />
            </div>
            <div className="min-w-0">
              <h2 className="text-lg font-bold text-slate-900 dark:text-white leading-tight">
                {formatName(plugin.name)}
              </h2>
              {plugin.version && (
                <span className="text-xs text-muted-foreground mt-1 block">v{plugin.version}</span>
              )}
            </div>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground transition-colors shrink-0 ml-2">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          {plugin.description && (
            <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
              {plugin.description}
            </p>
          )}

          {/* Components summary */}
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
              Components
            </h3>
            <div className="flex flex-wrap gap-2">
              <StatPill count={plugin.agent_count}   label="agents"   color="bg-violet-100 text-violet-700 dark:bg-violet-950 dark:text-violet-300" />
              <StatPill count={plugin.skill_count}   label="skills"   color="bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300" />
              <StatPill count={plugin.command_count} label="commands" color="bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300" />
              <BoolPill active={plugin.has_hooks} label="hooks" />
              <BoolPill active={plugin.has_mcp}   label="MCP servers" />
              <BoolPill active={plugin.has_lsp}   label="LSP" />
              {!plugin.agent_count && !plugin.skill_count && !plugin.command_count &&
               !plugin.has_hooks && !plugin.has_mcp && !plugin.has_lsp && (
                <span className="text-xs text-muted-foreground">None indexed</span>
              )}
            </div>
          </div>

          {/* Agents — collapsible */}
          {plugin.agents.length > 0 && (
            <div>
              <button
                className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors mb-3 w-full text-left"
                onClick={() => setAgentsExpanded(e => !e)}
              >
                {agentsExpanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                Agents ({plugin.agents.length})
                {agentLoading && <Loader2 className="h-3 w-3 ml-1 animate-spin" />}
              </button>

              {agentsExpanded && (
                <div className="space-y-1.5">
                  {agentLoading && (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground py-3">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Loading agent files…
                    </div>
                  )}
                  {agentError && (
                    <div className="flex items-center gap-2">
                      <p className="text-xs text-red-500">{agentError}</p>
                      <button onClick={retry} className="text-xs text-violet-500 hover:underline">Retry</button>
                    </div>
                  )}
                  {agentData
                    ? agentData.map(agent => <AgentRow key={agent.slug} agent={agent} />)
                    : !agentLoading && !agentError && plugin.agents.map(slug => (
                        <div key={slug} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                          <div className="h-1.5 w-1.5 rounded-full bg-violet-400 shrink-0" />
                          <span className="text-xs text-slate-600 dark:text-slate-400">{formatName(slug)}</span>
                        </div>
                      ))
                  }
                </div>
              )}
            </div>
          )}

          {/* Keywords */}
          {(plugin.keywords ?? []).length > 0 && (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">Tags</h3>
              <div className="flex flex-wrap gap-1.5">
                {(plugin.keywords ?? []).map(kw => (
                  <span key={kw} className="text-xs bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 px-2.5 py-1 rounded-lg">
                    {kw}
                  </span>
                ))}
              </div>
            </div>
          )}

          {plugin.homepage && (
            <div className="pt-2 border-t">
              <a
                href={plugin.homepage}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-sm text-violet-600 dark:text-violet-400 hover:underline"
              >
                <ExternalLink className="h-3.5 w-3.5" />
                View on GitHub
              </a>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

// ── page ──────────────────────────────────────────────────────────────────────

export function PluginsCataloguePage() {
  const [plugins, setPlugins]   = useState<Plugin[]>([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState<string | null>(null)
  const [search, setSearch]     = useState('')
  const [selected, setSelected] = useState<Plugin | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await apiClient.listPlugins()
      setPlugins(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const filtered = plugins.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase()) ||
    p.description.toLowerCase().includes(search.toLowerCase()) ||
    (p.keywords ?? []).some(k => k.toLowerCase().includes(search.toLowerCase()))
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    )
  }

  return (
    <div className="flex-1 p-8 relative min-h-screen">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-100 via-transparent to-transparent opacity-50 dark:from-slate-800/40 dark:via-background dark:to-background pointer-events-none -z-10" />

      <div className="relative z-10 max-w-6xl mx-auto space-y-6">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
              <Puzzle className="w-6 h-6 text-violet-500" />
              Plugins Catalogue
            </h1>
            <p className="text-muted-foreground mt-1">Browse Claude Code plugins from razorpay/claude-plugins</p>
          </div>
          <div className="text-sm text-muted-foreground">
            {filtered.length} of {plugins.length} plugins
          </div>
        </div>

        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search plugins..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="pl-10"
          />
        </div>

        {error && (
          <div className="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-4 flex items-center justify-between">
            <p className="text-red-700 dark:text-red-300 text-sm">{error}</p>
            <Button size="sm" variant="outline" onClick={load} className="gap-1.5 shrink-0">
              <RefreshCw className="h-3.5 w-3.5" />
              Retry
            </Button>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map(plugin => (
            <PluginCard key={plugin.plugin_dir} plugin={plugin} onClick={() => setSelected(plugin)} />
          ))}
          {filtered.length === 0 && (
            <div className="col-span-3 text-center py-16">
              <Puzzle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground">No plugins found matching your search</p>
            </div>
          )}
        </div>
      </div>

      {selected && <PluginDrawer plugin={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}

export default PluginsCataloguePage
