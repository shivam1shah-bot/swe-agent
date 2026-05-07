import { cn } from '@/lib/utils'

interface PulseRepoFilterProps {
  repos: string[]
  active: string | null
  onChange: (repo: string | null) => void
}

export function PulseRepoFilter({ repos, active, onChange }: PulseRepoFilterProps) {
  if (!repos || repos.length === 0) return null

  const options: (string | null)[] = [null, ...repos]

  return (
    <div className="flex gap-1.5 flex-wrap mb-4">
      {options.map(repo => (
        <button
          key={repo || 'all'}
          onClick={() => onChange(repo)}
          className={cn(
            'font-mono text-[11px] px-3 py-1 rounded-full border transition-all cursor-pointer',
            active === repo
              ? 'bg-blue-500/10 border-blue-500 text-blue-500'
              : 'bg-muted border-border text-muted-foreground hover:border-blue-500 hover:text-blue-500'
          )}
        >
          {repo || 'All repos'}
        </button>
      ))}
    </div>
  )
}
