import { cn } from '@/lib/utils'

const RANK_COLORS: Record<number, string> = {
  1: 'text-yellow-400',
  2: 'text-gray-300',
  3: 'text-amber-600',
}

interface PulseRankBadgeProps {
  rank: number
  showMedal?: boolean
}

export function PulseRankBadge({ rank, showMedal = false }: PulseRankBadgeProps) {
  if (showMedal && rank <= 3) {
    const medals = ['', '🥇', '🥈', '🥉']
    return <span className="text-lg">{medals[rank]}</span>
  }

  return (
    <span className={cn('font-mono text-sm font-semibold text-center', RANK_COLORS[rank] || 'text-muted-foreground')}>
      {rank}
    </span>
  )
}
