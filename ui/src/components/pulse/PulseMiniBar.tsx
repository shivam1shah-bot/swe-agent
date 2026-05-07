interface PulseMiniBarProps {
  percentage: number
}

export function PulseMiniBar({ percentage }: PulseMiniBarProps) {
  const clamped = Math.max(0, Math.min(100, percentage))

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-1000 ease-out bg-gradient-to-r from-green-500 to-cyan-500"
          style={{ width: `${clamped}%` }}
        />
      </div>
      <span className="font-mono text-[11px] font-semibold text-green-500 min-w-[36px] text-right">
        {clamped}%
      </span>
    </div>
  )
}
