import { cn } from '@/lib/utils'

const TAG_STYLES: Record<string, string> = {
  write: 'bg-green-500/10 text-green-500',
  read: 'bg-blue-500/10 text-blue-500',
  mixed: 'bg-purple-500/10 text-purple-500',
  text: 'bg-muted text-muted-foreground',
  model: 'bg-amber-500/10 text-amber-500',
  sha: 'bg-cyan-500/10 text-cyan-500 font-mono',
}

interface PulseTagProps {
  type: string
  children?: React.ReactNode
}

export function PulseTag({ type, children }: PulseTagProps) {
  const style = TAG_STYLES[type] || TAG_STYLES.text
  return (
    <span className={cn('inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wide', style)}>
      {children || type}
    </span>
  )
}
