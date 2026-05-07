import { useState } from 'react'
import { Card } from '@/components/ui/card'
import { usePulseRepos } from '@/hooks/usePulseData'
import { PulseSortBar } from '@/components/pulse/PulseSortBar'
import { PulseRankBadge } from '@/components/pulse/PulseRankBadge'
import { PulseMiniBar } from '@/components/pulse/PulseMiniBar'
import { PulseTag } from '@/components/pulse/PulseTag'
import { PulsePagination } from '@/components/pulse/PulsePagination'
import { PulseContributorsModal } from '@/components/pulse/PulseContributorsModal'
import { fmtCost, fmtTokens, modelShort } from '@/types/pulse'
import type { PulseRepo } from '@/types/pulse'

const SORT_OPTIONS = [
  { label: 'Cost \u2193', value: 'cost' },
  { label: 'Tokens \u2193', value: 'tokens' },
  { label: 'AI % \u2193', value: 'ai_pct' },
  { label: 'Prompts \u2193', value: 'prompts' },
  { label: 'AI Lines \u2193', value: 'ai_lines' },
]

const PAGE_SIZE = 20

export function PulseRepositoriesPage() {
  const [sort, setSort] = useState('cost')
  const [offset, setOffset] = useState(0)
  const [modalRepo, setModalRepo] = useState<PulseRepo | null>(null)

  const { data, isLoading, error, refetch } = usePulseRepos({ days: 30, sort, limit: PAGE_SIZE, offset })

  const handleSort = (s: string) => { setSort(s); setOffset(0) }

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

  if (!data?.repos?.length) {
    return <div className="text-center py-20 text-muted-foreground">No repository data</div>
  }

  return (
    <div className={isLoading ? 'opacity-60 pointer-events-none transition-opacity' : 'transition-opacity'}>
      <PulseSortBar options={SORT_OPTIONS} active={sort} onChange={handleSort} />

      <Card>
        <div className="grid grid-cols-[40px_1fr_90px_90px_90px_110px_70px_60px] px-5 py-2.5 bg-muted border-b border-border text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
          <span>#</span>
          <span>Repository</span>
          <span className="text-right">Cost</span>
          <span className="text-right">Tokens</span>
          <span className="text-right">Prompts</span>
          <span className="pl-3">AI %</span>
          <span className="text-right">Commits</span>
          <span className="text-right">Devs</span>
        </div>

        {data.repos.map((r: PulseRepo) => (
          <div
            key={r.repo}
            className="grid grid-cols-[40px_1fr_90px_90px_90px_110px_70px_60px] items-center px-5 py-3 border-b border-border last:border-b-0 hover:bg-muted/50 transition-colors"
          >
            <PulseRankBadge rank={r.rank} />
            <div className="min-w-0">
              <div className="text-sm font-medium text-foreground truncate">{r.repo}</div>
              <div className="text-[11px] text-muted-foreground mt-0.5 flex items-center gap-1 flex-wrap">
                {r.contributors} contributor{r.contributors !== 1 ? 's' : ''}
                {r.models?.map(m => (
                  <PulseTag key={m} type="model">{modelShort(m)}</PulseTag>
                ))}
              </div>
            </div>
            <div className="font-mono text-sm font-semibold text-amber-500 text-right">{fmtCost(r.total_cost_usd)}</div>
            <div className="font-mono text-sm text-blue-500 text-right">{fmtTokens(r.total_tokens)}</div>
            <div className="font-mono text-sm text-foreground text-right">{r.total_prompts}</div>
            <div className="pl-3"><PulseMiniBar percentage={r.ai_percentage} /></div>
            <div className="font-mono text-sm text-foreground text-right">{r.commits}</div>
            <div
              className="font-mono text-sm text-blue-500 text-right cursor-pointer hover:underline"
              onClick={() => setModalRepo(r)}
            >
              {r.contributors}
            </div>
          </div>
        ))}
      </Card>

      <PulsePagination total={data?.total ?? 0} limit={PAGE_SIZE} offset={offset} onPageChange={setOffset} />

      <PulseContributorsModal
        repo={modalRepo?.repo ?? ''}
        contributors={modalRepo?.contributor_list}
        open={!!modalRepo}
        onClose={() => setModalRepo(null)}
      />
    </div>
  )
}
