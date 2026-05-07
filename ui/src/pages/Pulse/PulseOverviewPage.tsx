import { useState } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { usePulseOverview } from '@/hooks/usePulseData'
import { usePulsePrompts } from '@/hooks/usePulseData'
import { PulseWeeklyCostChart } from '@/components/pulse/PulseWeeklyCostChart'
import { PulseModelDistribution, PulsePromptTypes } from '@/components/pulse/PulseModelDistribution'
import { PulsePromptDetailModal } from '@/components/pulse/PulsePromptDetailModal'
import { PulseTag } from '@/components/pulse/PulseTag'
import { PulseTooltipIcon } from '@/components/pulse/PulseTooltipIcon'
import { fmtCost, fmtTokens, fmtTime, fmtCompact, modelShort, pulseTooltips } from '@/types/pulse'
import type { PulsePromptDetail } from '@/types/pulse'
import { DollarSign, Activity, Zap, GitBranch, Database } from 'lucide-react'

interface StatCardProps {
  label: string
  value: number
  decimals?: number
  prefix?: string
  sub?: string
  tooltip?: string
  formatter?: (n: number) => string
  icon: React.ComponentType<{ className?: string }>
  accentClass: string
}

function StatCard({ label, value, prefix = '', sub, tooltip, formatter, icon: Icon, accentClass }: StatCardProps) {
  const formatted = formatter
    ? formatter(value)
    : prefix + (value >= 1 ? value.toFixed(2) : value >= 0.001 ? value.toFixed(4) : Math.round(value).toLocaleString())

  return (
    <Card className="relative overflow-visible hover:-translate-y-0.5 hover:shadow-lg transition-all">
      <CardContent className="p-5">
        <div className="flex items-center gap-1.5 mb-2">
          <Icon className={`h-3.5 w-3.5 ${accentClass}`} />
          <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">{label}</span>
          {tooltip && <PulseTooltipIcon text={tooltip} />}
        </div>
        <div className={`font-mono text-2xl font-semibold leading-none ${accentClass}`}>
          {formatted}
        </div>
        {sub && <div className="text-[11px] text-muted-foreground mt-1.5">{sub}</div>}
      </CardContent>
    </Card>
  )
}

export function PulseOverviewPage() {
  const [days] = useState<number | null>(30)
  const { data, isLoading, error, refetch } = usePulseOverview(days)
  const { data: recentData } = usePulsePrompts({ days, limit: 8, sort: 'newest' })
  const [modalPrompt, setModalPrompt] = useState<PulsePromptDetail | null>(null)

  if (isLoading && !data) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-20">
        <p className="text-destructive mb-2">{error}</p>
        <button onClick={refetch} className="text-sm text-primary underline">Retry</button>
      </div>
    )
  }

  if (!data) {
    return <div className="text-center py-20 text-muted-foreground">No overview data available</div>
  }

  const kpis: StatCardProps[] = [
    { label: 'Total Cost', value: data.total_cost_usd ?? 0, prefix: '$', accentClass: 'text-amber-500', sub: 'estimated USD', tooltip: pulseTooltips.totalCost, icon: DollarSign },
    { label: 'Total Tokens', value: data.total_tokens, accentClass: 'text-blue-500', sub: 'all turns combined', tooltip: pulseTooltips.totalTokens, formatter: fmtCompact, icon: Activity },
    { label: 'Total Prompts', value: data.total_prompts ?? 0, accentClass: 'text-purple-500', sub: 'all prompts', tooltip: pulseTooltips.totalPrompts, formatter: fmtCompact, icon: Zap },
    { label: 'AI Lines', value: data.total_ai_lines, accentClass: 'text-green-500', sub: `${data.ai_percentage ?? 0}% of committed code`, tooltip: pulseTooltips.aiLines, formatter: fmtCompact, icon: GitBranch },
    { label: 'Cache Savings', value: data.cache_saved_usd ?? 0, prefix: '$', accentClass: 'text-cyan-500', sub: 'vs full input price', tooltip: pulseTooltips.cacheSavings, icon: DollarSign },
    { label: 'Repos Tracked', value: data.repo_count ?? 0, accentClass: 'text-blue-500', sub: 'active repositories', tooltip: pulseTooltips.reposTracked, formatter: fmtCompact, icon: Database },
  ]

  return (
    <div className={isLoading ? 'opacity-60 pointer-events-none transition-opacity' : 'transition-opacity'}>
      {/* KPI Grid */}
      <div className="grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-3.5 mb-7">
        {kpis.map((k) => (
          <StatCard key={k.label} {...k} />
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-4 mb-7">
        <PulseWeeklyCostChart data={data.weekly} />
        <div className="flex flex-col gap-4">
          <PulseModelDistribution data={data.model_distribution} />
          <PulsePromptTypes data={data.turn_type_dist} />
        </div>
      </div>

      {/* Recent Prompts */}
      <div className="mb-4">
        <div className="flex items-center gap-2 mb-3">
          <h3 className="text-base font-bold text-foreground">Recent Prompts</h3>
          <PulseTooltipIcon text="The most recent AI prompts sent across all repos, ordered by time." />
        </div>
      </div>

      <Card>
        <div className="grid grid-cols-[1fr_180px_80px_80px] px-5 py-2.5 bg-muted border-b border-border text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
          <span>Prompt</span>
          <span>Model / Type</span>
          <span className="text-right">Tokens</span>
          <span className="text-right">Cost</span>
        </div>
        {recentData?.prompts && recentData.prompts.length > 0 ? (
          recentData.prompts.map((p: PulsePromptDetail, i: number) => (
            <div
              key={p.prompt_id ?? i}
              onClick={() => setModalPrompt(p)}
              className="grid grid-cols-[1fr_180px_80px_80px] items-center px-5 py-3 border-b border-border last:border-b-0 hover:bg-muted/50 cursor-pointer transition-colors"
            >
              <div className="min-w-0">
                <div className="text-sm font-medium text-foreground truncate">
                  {(p.prompt || '').slice(0, 120)}{(p.prompt || '').length > 120 ? '\u2026' : ''}
                </div>
                <div className="text-[11px] text-muted-foreground mt-0.5 truncate">
                  {p.author || 'unknown'} &middot; {p.repo || ''} &middot; {fmtTime(p.timestamp)}
                </div>
              </div>
              <div className="flex items-center gap-1.5 pl-2">
                {p.model && <PulseTag type="model">{modelShort(p.model)}</PulseTag>}
                <PulseTag type={p.turn_type} />
              </div>
              <div className="font-mono text-sm text-foreground text-right">
                {fmtTokens(p.total_tokens)}
              </div>
              <div className="font-mono text-sm font-semibold text-amber-500 text-right">
                {fmtCost(p.cost_usd)}
              </div>
            </div>
          ))
        ) : (
          <div className="text-center py-10 text-muted-foreground">No prompts recorded yet</div>
        )}
      </Card>

      <PulsePromptDetailModal prompt={modalPrompt} open={!!modalPrompt} onClose={() => setModalPrompt(null)} />
    </div>
  )
}
