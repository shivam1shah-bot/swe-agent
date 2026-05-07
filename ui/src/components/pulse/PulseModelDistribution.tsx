import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { modelShort } from '@/types/pulse'

const COLORS = [
  'hsl(var(--chart-1))',
  'hsl(var(--chart-3))',
  'hsl(var(--chart-2))',
  'hsl(var(--chart-4))',
  'hsl(var(--chart-5))',
]

const TURN_COLORS: Record<string, string> = {
  write: 'hsl(var(--chart-2))',
  read: 'hsl(var(--chart-1))',
  mixed: 'hsl(var(--chart-3))',
  text: 'hsl(var(--muted-foreground))',
}

interface PulseModelDistributionProps {
  data: Record<string, number> | undefined
}

export function PulseModelDistribution({ data }: PulseModelDistributionProps) {
  if (!data || Object.keys(data).length === 0) return null

  const entries = Object.entries(data).sort((a, b) => b[1] - a[1])
  const max = entries[0][1]
  if (max === 0) return null

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          Model Distribution
        </CardTitle>
        <p className="text-[10px] text-muted-foreground">Prompts per model</p>
      </CardHeader>
      <CardContent>
        <div className="space-y-2.5">
          {entries.map(([model, count], i) => {
            const pct = Math.round((count / max) * 100)
            return (
              <div key={model} className="flex items-center gap-2.5">
                <span className="font-mono text-[11px] text-muted-foreground min-w-[100px] truncate" title={model}>
                  {modelShort(model) || model}
                </span>
                <div className="flex-1 h-2.5 rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-1000 ease-out"
                    style={{ width: `${pct}%`, background: COLORS[i % COLORS.length] }}
                  />
                </div>
                <span className="font-mono text-[11px] font-semibold min-w-[35px] text-right" style={{ color: COLORS[i % COLORS.length] }}>
                  {count}
                </span>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}

interface PulsePromptTypesProps {
  data: Record<string, number> | undefined
}

export function PulsePromptTypes({ data }: PulsePromptTypesProps) {
  if (!data || Object.keys(data).length === 0) return null

  const entries = Object.entries(data).sort((a, b) => b[1] - a[1])
  const max = entries[0][1]
  if (max === 0) return null
  const total = entries.reduce((sum, [, c]) => sum + c, 0)

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          Prompt Types
        </CardTitle>
        <p className="text-[10px] text-muted-foreground">
          write = code changes, read = code reading, text = conversation
        </p>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {entries.map(([type, count]) => {
            const pct = total > 0 ? Math.round((count / total) * 100) : 0
            return (
              <div key={type} className="flex items-center gap-2.5">
                <span className="font-mono text-[11px] text-muted-foreground min-w-[50px] capitalize">
                  {type}
                </span>
                <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-1000 ease-out"
                    style={{ width: `${(count / max) * 100}%`, background: TURN_COLORS[type] || 'hsl(var(--muted-foreground))' }}
                  />
                </div>
                <span className="font-mono text-[10px] text-muted-foreground min-w-[55px] text-right">
                  {count} ({pct}%)
                </span>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
