import { useState, useContext } from 'react'
import { Card } from '@/components/ui/card'
import { usePulsePeople } from '@/hooks/usePulseData'
import { PulseReposContext } from '@/pages/Pulse'
import { PulseSortBar } from '@/components/pulse/PulseSortBar'
import { PulseRepoFilter } from '@/components/pulse/PulseRepoFilter'
import { PulseRankBadge } from '@/components/pulse/PulseRankBadge'
import { PulsePagination } from '@/components/pulse/PulsePagination'
import { PulsePromptDetailModal } from '@/components/pulse/PulsePromptDetailModal'
import { fmtCost, fmtTokens, fmtTime } from '@/types/pulse'
import type { PulsePerson, PulsePromptDetail } from '@/types/pulse'
import { ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'

const SORT_OPTIONS = [
  { label: 'Cost \u2193', value: 'cost' },
  { label: 'Tokens \u2193', value: 'tokens' },
  { label: 'Prompts \u2193', value: 'prompts' },
  { label: 'AI Lines \u2193', value: 'lines' },
]

const PAGE_SIZE = 20

export function PulseLeaderboardPage() {
  const [sort, setSort] = useState('cost')
  const [repoFilter, setRepoFilter] = useState<string | null>(null)
  const [offset, setOffset] = useState(0)
  const [expanded, setExpanded] = useState<number | null>(null)
  const [modalPrompt, setModalPrompt] = useState<PulsePromptDetail | null>(null)

  const repos = useContext(PulseReposContext)

  const { data, isLoading, error, refetch } = usePulsePeople({ days: 30, sort, repo: repoFilter, limit: PAGE_SIZE, offset })

  const handleSort = (s: string) => { setSort(s); setOffset(0); setExpanded(null) }
  const handleRepo = (r: string | null) => { setRepoFilter(r); setOffset(0); setExpanded(null) }
  const handlePageChange = (newOffset: number) => { setOffset(newOffset); setExpanded(null) }

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

  if (!data?.people?.length) {
    return <div className="text-center py-20 text-muted-foreground">No developer data</div>
  }

  return (
    <div className={isLoading ? 'opacity-60 pointer-events-none transition-opacity' : 'transition-opacity'}>
      <PulseSortBar options={SORT_OPTIONS} active={sort} onChange={handleSort} />
      <PulseRepoFilter repos={repos} active={repoFilter} onChange={handleRepo} />

      <Card>
        <div className="grid grid-cols-[44px_1fr_80px_80px_80px_80px_80px] px-5 py-2.5 bg-muted border-b border-border text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
          <span>#</span>
          <span>Developer</span>
          <span className="text-right">Prompts</span>
          <span className="text-right">Writes</span>
          <span className="text-right">AI Lines</span>
          <span className="text-right">Tokens</span>
          <span className="text-right">Cost</span>
        </div>

        {data.people.map((p: PulsePerson, i: number) => {
          const isExpanded = expanded === i
          const hasPrompts = (p.top_prompts?.length ?? 0) > 0
          return (
            <div key={p.email} className="border-b border-border last:border-b-0">
              <div
                onClick={() => hasPrompts && setExpanded(isExpanded ? null : i)}
                className={cn(
                  'grid grid-cols-[44px_1fr_80px_80px_80px_80px_80px] items-center px-5 py-3 transition-colors',
                  hasPrompts && 'cursor-pointer hover:bg-muted/50',
                  isExpanded && 'bg-muted/50'
                )}
              >
                <PulseRankBadge rank={p.rank} showMedal />
                <div className="min-w-0">
                  <div className="text-sm font-medium text-foreground truncate flex items-center gap-1">
                    {p.email}
                    {hasPrompts && (
                      <ChevronRight
                        size={12}
                        className={cn('text-muted-foreground transition-transform', isExpanded && 'rotate-90')}
                      />
                    )}
                  </div>
                  <div className="text-[11px] text-muted-foreground mt-0.5 flex items-center gap-1 flex-wrap">
                    {p.repos?.map(r => (
                      <span key={r} className="inline-flex items-center bg-accent border border-border rounded px-1.5 py-px text-[10px] font-mono">
                        {r}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="font-mono text-sm text-blue-500 text-right">{p.total_prompts}</div>
                <div className="font-mono text-sm text-green-500 text-right">{p.write_prompts}</div>
                <div className="font-mono text-sm text-purple-500 text-right">{(p.ai_lines ?? 0).toLocaleString()}</div>
                <div className="font-mono text-sm text-blue-500 text-right">{fmtTokens(p.total_tokens)}</div>
                <div className="font-mono text-sm font-semibold text-amber-500 text-right">{fmtCost(p.total_cost_usd)}</div>
              </div>

              {isExpanded && hasPrompts && (
                <div className="px-5 py-3 pl-10 bg-blue-500/[0.03] border-t border-blue-500/[0.08]">
                  <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-[0.1em] mb-2.5">
                    Top prompts by cost
                  </div>
                  <div className="space-y-1.5">
                    {p.top_prompts!.map((pr, pi) => (
                      <div
                        key={pr.prompt_id ?? pi}
                        onClick={(e) => {
                          e.stopPropagation()
                          setModalPrompt({ ...pr, author: p.email } as PulsePromptDetail)
                        }}
                        className="bg-accent border border-border rounded-lg p-3 cursor-pointer hover:border-border/80 transition-colors grid grid-cols-[1fr_auto] gap-2"
                      >
                        <div className="text-xs text-muted-foreground leading-relaxed break-words">
                          {(pr.prompt || '').slice(0, 220)}{(pr.prompt || '').length > 220 ? '\u2026' : ''}
                        </div>
                        <div className="flex flex-col items-end gap-1 flex-shrink-0">
                          <span className="font-mono text-[11px] font-semibold text-amber-500">{fmtCost(pr.cost_usd)}</span>
                          <span className="text-[10px] text-muted-foreground font-mono text-right">
                            {fmtTokens(pr.total_tokens)} tok
                            <br />{pr.repo}
                            <br />{fmtTime(pr.timestamp)}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </Card>

      <PulsePagination total={data?.total ?? 0} limit={PAGE_SIZE} offset={offset} onPageChange={handlePageChange} />

      <PulsePromptDetailModal prompt={modalPrompt} open={!!modalPrompt} onClose={() => setModalPrompt(null)} />
    </div>
  )
}
