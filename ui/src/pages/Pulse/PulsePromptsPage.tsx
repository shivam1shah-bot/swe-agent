import { useState, useContext } from 'react'
import { Card } from '@/components/ui/card'
import { usePulsePrompts } from '@/hooks/usePulseData'
import { PulseReposContext } from '@/pages/Pulse'
import { PulseSortBar } from '@/components/pulse/PulseSortBar'
import { PulseRepoFilter } from '@/components/pulse/PulseRepoFilter'
import { PulseRankBadge } from '@/components/pulse/PulseRankBadge'
import { PulseTag } from '@/components/pulse/PulseTag'
import { PulsePagination } from '@/components/pulse/PulsePagination'
import { PulsePromptDetailModal } from '@/components/pulse/PulsePromptDetailModal'
import { fmtCost, fmtTokens, fmtTime, modelShort } from '@/types/pulse'
import type { PulsePromptDetail } from '@/types/pulse'

const SORT_OPTIONS = [
  { label: 'Cost \u2193', value: 'cost' },
  { label: 'Total Tokens \u2193', value: 'tokens' },
  { label: 'Output Tokens \u2193', value: 'output' },
  { label: 'Newest', value: 'newest' },
]

const PAGE_SIZE = 20

export function PulsePromptsPage() {
  const [sort, setSort] = useState('cost')
  const [repoFilter, setRepoFilter] = useState<string | null>(null)
  const [offset, setOffset] = useState(0)
  const [modalPrompt, setModalPrompt] = useState<PulsePromptDetail | null>(null)

  const repos = useContext(PulseReposContext)

  const { data, isLoading, error, refetch } = usePulsePrompts({ days: 30, sort, repo: repoFilter, limit: PAGE_SIZE, offset })

  const handleSort = (s: string) => { setSort(s); setOffset(0) }
  const handleRepo = (r: string | null) => { setRepoFilter(r); setOffset(0) }

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
        <div className="grid grid-cols-[40px_1fr_110px_80px_90px_80px] px-5 py-2.5 bg-muted border-b border-border text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
          <span>#</span>
          <span>Prompt</span>
          <span>Author</span>
          <span>Repo</span>
          <span className="text-right">Tokens</span>
          <span className="text-right">Cost</span>
        </div>

        {data?.prompts?.length ? (
          data.prompts.map((p: PulsePromptDetail, i: number) => (
            <div
              key={p.prompt_id ?? i}
              onClick={() => setModalPrompt(p)}
              className="grid grid-cols-[40px_1fr_110px_80px_90px_80px] items-center px-5 py-3 border-b border-border last:border-b-0 hover:bg-muted/50 cursor-pointer transition-colors"
            >
              <PulseRankBadge rank={p.rank} />
              <div className="min-w-0">
                <div className="text-sm font-medium text-foreground truncate">
                  {(p.prompt || '').slice(0, 90)}{(p.prompt || '').length > 90 ? '\u2026' : ''}
                </div>
                <div className="text-[11px] text-muted-foreground mt-0.5 flex items-center gap-1">
                  <PulseTag type={p.turn_type} />
                  {p.model && <PulseTag type="model">{modelShort(p.model)}</PulseTag>}
                  <span>{fmtTime(p.timestamp)}</span>
                </div>
              </div>
              <div className="text-xs text-foreground truncate">
                {(p.author || '').split('@')[0]}
              </div>
              <div>
                <span className="inline-flex items-center gap-1 bg-accent border border-border rounded px-2 py-0.5 text-[11px] text-muted-foreground font-mono">
                  {p.repo}
                </span>
              </div>
              <div className="font-mono text-sm text-blue-500 text-right">{fmtTokens(p.total_tokens)}</div>
              <div className="font-mono text-sm font-semibold text-amber-500 text-right">{fmtCost(p.cost_usd)}</div>
            </div>
          ))
        ) : (
          <div className="py-10 text-center text-muted-foreground">No prompts found</div>
        )}
      </Card>

      <PulsePagination total={data?.total ?? 0} limit={PAGE_SIZE} offset={offset} onPageChange={setOffset} />

      <PulsePromptDetailModal prompt={modalPrompt} open={!!modalPrompt} onClose={() => setModalPrompt(null)} />
    </div>
  )
}
