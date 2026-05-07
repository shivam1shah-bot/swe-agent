import { useState, useContext } from 'react'
import { Card } from '@/components/ui/card'
import { usePulseCommits } from '@/hooks/usePulseData'
import { PulseReposContext } from '@/pages/Pulse'
import { PulseSortBar } from '@/components/pulse/PulseSortBar'
import { PulseRepoFilter } from '@/components/pulse/PulseRepoFilter'
import { PulseRankBadge } from '@/components/pulse/PulseRankBadge'
import { PulseMiniBar } from '@/components/pulse/PulseMiniBar'
import { PulseTag } from '@/components/pulse/PulseTag'
import { PulsePagination } from '@/components/pulse/PulsePagination'
import { PulsePromptDetailModal } from '@/components/pulse/PulsePromptDetailModal'
import { fmtCost, fmtTokens, modelShort } from '@/types/pulse'
import type { PulseCommit, PulsePromptDetail } from '@/types/pulse'
import { ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'

const SORT_OPTIONS = [
  { label: 'Date \u2193', value: 'date' },
  { label: 'Cost \u2193', value: 'cost' },
  { label: 'Tokens \u2193', value: 'tokens' },
  { label: 'AI % \u2193', value: 'ai_pct' },
  { label: 'AI Lines \u2193', value: 'ai_lines' },
  { label: 'Prompts \u2193', value: 'prompts' },
]

const PAGE_SIZE = 20

export function PulseCommitsPage() {
  const [sort, setSort] = useState('date')
  const [repoFilter, setRepoFilter] = useState<string | null>(null)
  const [offset, setOffset] = useState(0)
  const [expanded, setExpanded] = useState<number | null>(null)
  const [modalPrompt, setModalPrompt] = useState<PulsePromptDetail | null>(null)

  const repos = useContext(PulseReposContext)

  const { data, isLoading, error, refetch } = usePulseCommits({ days: 30, sort, repo: repoFilter, limit: PAGE_SIZE, offset })

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

  return (
    <div className={isLoading ? 'opacity-60 pointer-events-none transition-opacity' : 'transition-opacity'}>
      <PulseSortBar options={SORT_OPTIONS} active={sort} onChange={handleSort} />
      <PulseRepoFilter repos={repos} active={repoFilter} onChange={handleRepo} />

      <Card>
        <div className="grid grid-cols-[40px_90px_1fr_130px_110px_80px_80px] px-5 py-2.5 bg-muted border-b border-border text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
          <span>#</span>
          <span>SHA</span>
          <span>Commit</span>
          <span>Author / Branch</span>
          <span>AI %</span>
          <span className="text-right">Tokens</span>
          <span className="text-right">Cost</span>
        </div>

        {!data?.commits?.length ? (
          <div className="py-12 text-center text-muted-foreground">No commits found</div>
        ) : (
          data.commits.map((c: PulseCommit, i: number) => {
            const isExpanded = expanded === i
            const hasPrompts = (c.prompts?.length ?? 0) > 0
            return (
              <div key={c.commit_sha} className="border-b border-border last:border-b-0">
                <div
                  onClick={() => setExpanded(isExpanded ? null : i)}
                  className={cn(
                    'grid grid-cols-[40px_90px_1fr_130px_110px_80px_80px] items-center px-5 py-3 transition-colors cursor-pointer hover:bg-muted/50',
                    isExpanded && 'bg-muted/50'
                  )}
                >
                  <PulseRankBadge rank={c.rank} />
                  <PulseTag type="sha">{c.commit_sha}</PulseTag>
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-foreground truncate flex items-center gap-1">
                      {(c.commit_message || '').slice(0, 70)}{(c.commit_message || '').length > 70 ? '\u2026' : ''}
                      <ChevronRight
                        size={12}
                        className={cn('text-muted-foreground transition-transform flex-shrink-0', isExpanded && 'rotate-90')}
                      />
                    </div>
                    <div className="text-[11px] text-muted-foreground mt-0.5">
                      {c.repo} &middot; {c.prompt_count} prompt{c.prompt_count !== 1 ? 's' : ''}
                    </div>
                  </div>
                  <div className="min-w-0">
                    <div className="text-xs text-foreground truncate">{c.commit_author}</div>
                    <div className="text-[11px] text-muted-foreground truncate">{c.branch}</div>
                  </div>
                  <PulseMiniBar percentage={c.ai_percentage} />
                  <div className="font-mono text-sm text-blue-500 text-right">{fmtTokens(c.total_tokens)}</div>
                  <div className="font-mono text-sm font-semibold text-amber-500 text-right">{fmtCost(c.cost_usd)}</div>
                </div>

                {isExpanded && (
                  <div className="px-5 py-3 pl-10 bg-blue-500/[0.03] border-t border-blue-500/[0.08]">
                    <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-[0.1em] mb-2.5">
                      Prompts used in this commit ({c.prompts?.length ?? 0})
                    </div>
                    {hasPrompts ? (
                      <div className="space-y-1.5">
                        {c.prompts!.map((p, pi) => (
                          <div
                            key={`${p.timestamp}-${p.model}-${pi}`}
                            onClick={(e) => {
                              e.stopPropagation()
                              setModalPrompt({
                                ...p,
                                repo: c.repo,
                                branch: p.branch || c.branch,
                                author: p.author || c.commit_author,
                                rank: 0,
                                input_tokens: p.input_tokens ?? 0,
                                output_tokens: p.output_tokens ?? 0,
                                cache_read_tokens: p.cache_read_tokens ?? 0,
                                cache_creation_tokens: p.cache_creation_tokens ?? 0,
                                timestamp: p.timestamp ?? '',
                              } as PulsePromptDetail)
                            }}
                            className="bg-accent border border-border rounded-lg p-3 cursor-pointer hover:border-border/80 transition-colors grid grid-cols-[1fr_auto] gap-2"
                          >
                            <div className="text-xs text-muted-foreground leading-relaxed break-words">
                              {(p.prompt || '').slice(0, 200)}{(p.prompt || '').length > 200 ? '\u2026' : ''}
                            </div>
                            <div className="flex flex-col items-end gap-1 flex-shrink-0">
                              {p.cost_usd > 0 && (
                                <span className="font-mono text-[11px] font-semibold text-amber-500">{fmtCost(p.cost_usd)}</span>
                              )}
                              <span className="text-[10px] text-muted-foreground font-mono text-right">
                                {p.model && modelShort(p.model)}
                                {p.total_tokens > 0 && <><br />{fmtTokens(p.total_tokens)} tok</>}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-muted-foreground italic">No prompts recorded for this commit.</p>
                    )}
                  </div>
                )}
              </div>
            )
          })
        )}
      </Card>

      <PulsePagination total={data?.total ?? 0} limit={PAGE_SIZE} offset={offset} onPageChange={handlePageChange} />

      <PulsePromptDetailModal prompt={modalPrompt} open={!!modalPrompt} onClose={() => setModalPrompt(null)} />
    </div>
  )
}
