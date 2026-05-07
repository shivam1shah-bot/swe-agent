import { useState, useMemo, useEffect, useCallback } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import {
  LayoutGrid,
  CheckCircle2,
  XCircle,
  ChevronDown,
  ExternalLink,
  MessageSquare,
  Users,
  GitBranch,
  Search,
  Filter,
  ArrowUpRight,
  Loader2,
  AlertCircle,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Tool, AiToolsData, AiHubStats, ToolType, ProdReadyStatus } from '@/types/ai-hub'

// ─── Data Fetching ─────────────────────────────────────────────────────────

const TOOLS_JSON_URL = '/data/ai-tools.json'

interface FetchState {
  data: AiToolsData | null
  loading: boolean
  error: string | null
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function getTypeStyles(type: ToolType | string) {
  switch (type.toLowerCase()) {
    case 'plugin':
      return 'bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-300 dark:border-blue-800'
    case 'mcp':
      return 'bg-purple-100 text-purple-700 border-purple-200 dark:bg-purple-950 dark:text-purple-300 dark:border-purple-800'
    case 'skill':
      return 'bg-emerald-100 text-emerald-700 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:border-emerald-800'
    case 'agent':
      return 'bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-800'
    case 'langgraph agent':
      return 'bg-orange-100 text-orange-700 border-orange-200 dark:bg-orange-950 dark:text-orange-300 dark:border-orange-800'
    case 'service':
      return 'bg-cyan-100 text-cyan-700 border-cyan-200 dark:bg-cyan-950 dark:text-cyan-300 dark:border-cyan-800'
    case 'platform':
      return 'bg-rose-100 text-rose-700 border-rose-200 dark:bg-rose-950 dark:text-rose-300 dark:border-rose-800'
    case 'multi-agent':
      return 'bg-pink-100 text-pink-700 border-pink-200 dark:bg-pink-950 dark:text-pink-300 dark:border-pink-800'
    default:
      return 'bg-muted text-muted-foreground border-border'
  }
}

function getLifecycleStyles(prodReady: ProdReadyStatus | string) {
  switch (prodReady.toLowerCase()) {
    case 'yes':
      return 'bg-green-100 text-green-700 border-green-200 dark:bg-green-950 dark:text-green-300 dark:border-green-800'
    case 'partially':
      return 'bg-yellow-100 text-yellow-700 border-yellow-200 dark:bg-yellow-950 dark:text-yellow-300 dark:border-yellow-800'
    case 'preview':
      return 'bg-orange-100 text-orange-700 border-orange-200 dark:bg-orange-950 dark:text-orange-300 dark:border-orange-800'
    default:
      return 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-950 dark:text-slate-300 dark:border-slate-800'
  }
}

function getLifecycleLabel(prodReady: ProdReadyStatus | string) {
  switch (prodReady.toLowerCase()) {
    case 'yes':
      return 'GA'
    case 'partially':
      return 'Partial'
    case 'preview':
      return 'Preview'
    default:
      return 'In Dev'
  }
}

function getStageIcon(stage: string) {
  const icons: Record<string, string> = {
    'Planning': '📋',
    'Coding': '💻',
    'Devstack': '🧰',
    'Testing': '🧪',
    'Reviews': '👀',
    'Infra': '⚙️',
    'Deployments': '🚀',
    'Harness': '🎯',
  }
  return icons[stage] || '🔧'
}



// ─── Components ──────────────────────────────────────────────────────────────

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <Card className="border">
      <CardContent className="p-4">
        <div className="text-2xl font-bold" style={{ color }}>{value}</div>
        <div className="text-xs text-muted-foreground">{label}</div>
      </CardContent>
    </Card>
  )
}

function ToolCard({ tool, onClick }: { tool: Tool; onClick: () => void }) {
  return (
    <Card
      className="cursor-pointer transition-all duration-200 hover:border-primary/50 hover:shadow-md group"
      onClick={onClick}
    >
      <CardContent className="p-4">
        <div className="flex items-start gap-3">
          <div className="text-2xl shrink-0">{tool.stageEmoji}</div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <span className="font-medium text-sm truncate">{tool.name}</span>
            </div>
            <div className="flex items-center gap-2 flex-wrap mb-2">
              <span className={cn('px-2 py-0.5 text-xs rounded-md border font-medium', getTypeStyles(tool.type))}>
                {tool.type}
              </span>
              <span className={cn('px-2 py-0.5 text-xs rounded-md border font-medium', getLifecycleStyles(tool.prodReady))}>
                {getLifecycleLabel(tool.prodReady)}
              </span>
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span className="truncate">{tool.poc}</span>
              <span>•</span>
              <span className="text-primary">{tool.team}</span>
            </div>
          </div>
          <ArrowUpRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity shrink-0 mt-1" />
        </div>
      </CardContent>
    </Card>
  )
}

function ToolDetailCard({ tool, isOpen: controlledIsOpen, onToggle }: { tool: Tool; isOpen?: boolean; onToggle?: () => void }) {
  const [internalIsOpen, setInternalIsOpen] = useState(false)
  const isOpen = controlledIsOpen ?? internalIsOpen
  const handleToggle = () => {
    if (onToggle) {
      onToggle()
    } else {
      setInternalIsOpen(!internalIsOpen)
    }
  }

  return (
    <Card className="overflow-hidden border" id={`detail-${tool.id}`}>
      <div
        className="p-5 cursor-pointer transition-colors hover:bg-muted/30"
        onClick={handleToggle}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-2">
              <span className="text-xl">{tool.stageEmoji}</span>
              <h3 className="font-semibold">{tool.name}</h3>
              <span className={cn('px-2 py-0.5 text-xs rounded-md border font-medium', getTypeStyles(tool.type))}>
                {tool.type}
              </span>
              <span className={cn('px-2 py-0.5 text-xs rounded-md border font-medium', getLifecycleStyles(tool.prodReady))}>
                {getLifecycleLabel(tool.prodReady)}
              </span>
            </div>
            <p className="text-sm text-muted-foreground mb-2">{tool.state}</p>
            <div className="flex items-center gap-3 text-xs text-muted-foreground flex-wrap">
              <span className="font-medium text-primary">{tool.stage}</span>
              <span>•</span>
              <span className="flex items-center gap-1">
                <Users className="h-3 w-3" />
                {tool.poc}
              </span>
              <span>•</span>
              <span>{tool.team}</span>
            </div>
          </div>
          <ChevronDown
            className={cn(
              'h-5 w-5 text-muted-foreground transition-transform duration-200 shrink-0 mt-1',
              isOpen && 'rotate-180'
            )}
            onClick={(e) => {
              e.stopPropagation()
              handleToggle()
            }}
          />
        </div>
      </div>

      {isOpen && (
        <CardContent className="pt-0 px-5 pb-5 border-t bg-muted/20">
          {/* Capabilities */}
          {tool.canDo.length > 0 && (
            <div className="mt-4">
              <div className="flex items-center gap-2 mb-3">
                <CheckCircle2 className="h-4 w-4 text-green-500" />
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Capabilities
                </span>
              </div>
              <ul className="space-y-2">
                {tool.canDo.map((item, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-300 bg-green-50 dark:bg-green-950/20 rounded-lg p-3 border border-green-100 dark:border-green-900/30"
                  >
                    <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0 mt-0.5" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Limitations */}
          {tool.cantDo.length > 0 && (
            <div className="mt-4">
              <div className="flex items-center gap-2 mb-3">
                <XCircle className="h-4 w-4 text-red-500" />
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Limitations
                </span>
              </div>
              <ul className="space-y-2">
                {tool.cantDo.map((item, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-300 bg-red-50 dark:bg-red-950/20 rounded-lg p-3 border border-red-100 dark:border-red-900/30"
                  >
                    <XCircle className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Links */}
          {(tool.docsLink || tool.slackChannel) && (
            <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t">
              {tool.docsLink && (
                <a
                  href={tool.docsLink}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 hover:bg-blue-200 dark:hover:bg-blue-900/50 transition-colors"
                  onClick={(e) => e.stopPropagation()}
                >
                  <ExternalLink className="h-3 w-3" />
                  Documentation
                </a>
              )}
              {tool.slackChannel && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                  <MessageSquare className="h-3 w-3" />
                  {tool.slackChannel}
                </span>
              )}
            </div>
          )}
        </CardContent>
      )}
    </Card>
  )
}

function StageSection({ 
  stage, 
  tools, 
  onToolClick 
}: { 
  stage: string; 
  tools: Tool[]; 
  onToolClick: (toolId: string) => void
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <span className="text-2xl">{getStageIcon(stage)}</span>
        <h2 className="text-lg font-semibold">{stage}</h2>
        <Badge variant="secondary" className="text-xs">
          {tools.length}
        </Badge>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
        {tools.map((tool) => (
          <ToolCard
            key={tool.id}
            tool={tool}
            onClick={() => onToolClick(tool.id)}
          />
        ))}
      </div>
    </div>
  )
}

function DetailsSection({ 
  tools,
  openDetailId,
  onToggleDetail 
}: { 
  tools: Tool[]
  openDetailId: string | null
  onToggleDetail: (toolId: string) => void
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <LayoutGrid className="h-5 w-5 text-violet-500" />
        <h2 className="text-lg font-semibold">Tool Details — Capabilities & Gaps</h2>
        <Badge variant="secondary" className="text-xs">
          {tools.length}
        </Badge>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {tools.map((tool) => (
          <ToolDetailCard 
            key={tool.id} 
            tool={tool} 
            isOpen={openDetailId === tool.id}
            onToggle={() => onToggleDetail(tool.id)}
          />
        ))}
      </div>
    </div>
  )
}

// ─── Main Page ───────────────────────────────────────────────────────────────

export function AiHubPage() {
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [openDetailId, setOpenDetailId] = useState<string | null>(null)
  const [fetchState, setFetchState] = useState<FetchState>({
    data: null,
    loading: true,
    error: null,
  })

  // Scroll to and open a detail card
  const scrollToDetail = useCallback((toolId: string) => {
    setOpenDetailId(toolId)
    const element = document.getElementById(`detail-${toolId}`)
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [])

  // Fetch tools data from JSON
  useEffect(() => {
    const fetchTools = async () => {
      try {
        const response = await fetch(TOOLS_JSON_URL)
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }
        const data: AiToolsData = await response.json()
        setFetchState({ data, loading: false, error: null })
      } catch (err) {
        setFetchState({
          data: null,
          loading: false,
          error: err instanceof Error ? err.message : 'Failed to load tools data',
        })
      }
    }

    fetchTools()
  }, [])

  const tools = useMemo(() => fetchState.data?.tools || [], [fetchState.data?.tools])
  const updated = fetchState.data?.updated || ''

  const stages = useMemo(() => {
    const uniqueStages = [...new Set(tools.map((t) => t.stage))]
    return uniqueStages
  }, [tools])

  const filteredTools = useMemo(() => {
    return tools.filter((tool) => {
      const matchesSearch = 
        !search || 
        tool.name.toLowerCase().includes(search.toLowerCase()) ||
        tool.poc.toLowerCase().includes(search.toLowerCase()) ||
        tool.team.toLowerCase().includes(search.toLowerCase())
      const matchesType = !typeFilter || tool.type.toLowerCase() === typeFilter.toLowerCase()
      const matchesStatus = !statusFilter || tool.prodReady.toLowerCase() === statusFilter.toLowerCase()
      return matchesSearch && matchesType && matchesStatus
    })
  }, [tools, search, typeFilter, statusFilter])

  const toolsByStage = useMemo(() => {
    const grouped: Record<string, Tool[]> = {}
    stages.forEach((stage) => {
      grouped[stage] = filteredTools.filter((t) => t.stage === stage)
    })
    return grouped
  }, [stages, filteredTools])

  const stats: AiHubStats = useMemo(() => {
    const total = tools.length
    const ga = tools.filter((t) => t.prodReady === 'Yes').length
    const preview = tools.filter((t) => t.prodReady === 'Partially' || t.prodReady === 'Preview').length
    const dev = tools.filter((t) => t.prodReady === 'No').length
    return { total, ga, preview, dev }
  }, [tools])

  const availableTypes = [...new Set(tools.map((t) => t.type))]

  // Loading state
  if (fetchState.loading) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-screen">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary mx-auto mb-4" />
          <p className="text-muted-foreground">Loading AI tools catalog...</p>
        </div>
      </div>
    )
  }

  // Error state
  if (fetchState.error) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-screen">
        <div className="text-center max-w-md">
          <AlertCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
          <h2 className="text-lg font-semibold mb-2">Failed to load tools</h2>
          <p className="text-sm text-muted-foreground mb-4">{fetchState.error}</p>
          <Button onClick={() => window.location.reload()}>Retry</Button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 p-6 relative min-h-screen">
      {/* Background ambient effects */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-100 via-transparent to-transparent opacity-50 dark:from-slate-800/40 dark:via-background dark:to-background pointer-events-none" />

      <div className="relative z-10 max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
                <LayoutGrid className="w-6 h-6 text-violet-500" />
                AI Stack Dashboard
              </h1>
              <p className="text-muted-foreground mt-1">
                Complete catalog of AI tools across the Razorpay engineering organization
              </p>
            </div>
            <div className="text-sm text-muted-foreground">
              Updated: <span className="font-medium">{updated}</span>
            </div>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <StatCard label="Total Tools" value={stats.total} color="#6366f1" />
          <StatCard label="GA (Production)" value={stats.ga} color="#22c55e" />
          <StatCard label="Preview/Partial" value={stats.preview} color="#f59e0b" />
          <StatCard label="In Development" value={stats.dev} color="#64748b" />
        </div>

        {/* Filters */}
        <Card className="border">
          <CardContent className="p-4">
            <div className="flex flex-col sm:flex-row gap-4">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search tools, POCs, or teams..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pl-9"
                />
              </div>
              <div className="flex gap-2 flex-wrap">
                <select
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value)}
                  className="px-3 py-2 rounded-md border bg-background text-sm"
                >
                  <option value="">All Types</option>
                  {availableTypes.map((type) => (
                    <option key={type} value={type}>{type}</option>
                  ))}
                </select>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="px-3 py-2 rounded-md border bg-background text-sm"
                >
                  <option value="">All Statuses</option>
                  <option value="Yes">GA</option>
                  <option value="Partially">Partial</option>
                  <option value="Preview">Preview</option>
                  <option value="No">In Dev</option>
                </select>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Info card */}
        <Card className="bg-gradient-to-r from-violet-50 to-purple-50 dark:from-violet-950/20 dark:to-purple-950/20 border-violet-200 dark:border-violet-800">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-lg bg-violet-100 dark:bg-violet-900/30">
                <GitBranch className="h-5 w-5 text-violet-600 dark:text-violet-400" />
              </div>
              <div>
                <h3 className="font-semibold text-sm text-slate-900 dark:text-white">
                  SDLC-Organized Tool Catalog
                </h3>
                <p className="text-sm text-muted-foreground mt-1">
                  Browse {stats.total}+ AI tools organized by software development lifecycle stages.
                  Each card shows production readiness, capabilities, and limitations.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Stages */}
        <div className="space-y-8">
          {stages.map((stage) => (
            toolsByStage[stage]?.length > 0 && (
              <StageSection
                key={stage}
                stage={stage}
                tools={toolsByStage[stage]}
                onToolClick={scrollToDetail}
              />
            )
          ))}
        </div>

        {/* Divider */}
        <div className="h-px bg-border my-8" />

        {/* Details Section */}
        <DetailsSection 
          tools={filteredTools}
          openDetailId={openDetailId}
          onToggleDetail={(name) => setOpenDetailId(openDetailId === name ? null : name)}
        />

        {/* Empty state */}
        {filteredTools.length === 0 && (
          <div className="text-center py-12">
            <Filter className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-medium">No tools found</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Try adjusting your search or filters
            </p>
            <Button
              variant="outline"
              className="mt-4"
              onClick={() => {
                setSearch('')
                setTypeFilter('')
                setStatusFilter('')
              }}
            >
              Clear filters
            </Button>
          </div>
        )}

        {/* Footer */}
        <div className="text-center pt-8 text-sm text-muted-foreground">
          Want to add or update a tool? Contact the DevEx team or open a PR.
        </div>
      </div>
    </div>
  )
}
