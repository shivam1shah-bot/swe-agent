import { cn } from '@/lib/utils'

interface SortOption {
  label: string
  value: string
}

interface PulseSortBarProps {
  options: SortOption[]
  active: string
  onChange: (value: string) => void
}

export function PulseSortBar({ options, active, onChange }: PulseSortBarProps) {
  return (
    <div className="flex items-center gap-2 mb-4 flex-wrap">
      <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        Sort by
      </span>
      {options.map(opt => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={cn(
            'font-mono text-[11px] px-3 py-1.5 rounded-md border transition-all cursor-pointer',
            active === opt.value
              ? 'bg-blue-500/10 border-blue-500 text-blue-500'
              : 'bg-muted border-border text-muted-foreground hover:border-blue-500 hover:text-blue-500'
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}
