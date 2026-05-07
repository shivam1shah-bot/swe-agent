import { ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import type { PulseWeeklyData } from '@/types/pulse'

interface ChartTooltipProps {
  active?: boolean
  payload?: Array<{ color: string; name: string; value: number }>
  label?: string
}

function ChartTooltip({ active, payload, label }: ChartTooltipProps) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-card border border-border rounded-lg p-3 shadow-xl text-xs">
      <div className="font-semibold text-card-foreground mb-1.5">{label}</div>
      {payload.map((entry, i) => (
        <div key={i} className="flex items-center gap-2 mb-0.5">
          <div className="w-2.5 h-2.5 rounded-sm" style={{ background: entry.color }} />
          <span className="text-muted-foreground">{entry.name}:</span>
          <span className="font-mono font-semibold text-card-foreground">
            {entry.name === 'Cost ($)' ? `$${entry.value.toFixed(4)}` : entry.value}
          </span>
        </div>
      ))}
    </div>
  )
}

interface PulseWeeklyCostChartProps {
  data: PulseWeeklyData[] | undefined
}

export function PulseWeeklyCostChart({ data }: PulseWeeklyCostChartProps) {
  if (!data || data.length === 0) return null

  const formatted = data.map(d => {
    const parts = (d.week || '').split('-W')
    return {
      ...d,
      weekLabel: parts.length === 2 ? 'W' + parts[1] : d.week || '\u2014',
    }
  })

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          Weekly Cost & Prompts
        </CardTitle>
        <p className="text-[10px] text-muted-foreground">
          Blue bars = AI cost per week &nbsp;|&nbsp; Green line = prompts sent
        </p>
      </CardHeader>
      <CardContent>
        <div className="h-[200px]">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={formatted} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
              <XAxis
                dataKey="weekLabel"
                tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                axisLine={{ stroke: 'hsl(var(--border))' }}
                tickLine={false}
              />
              <YAxis
                yAxisId="cost"
                tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: number) => `$${v >= 1 ? v.toFixed(0) : v.toFixed(2)}`}
              />
              <YAxis
                yAxisId="prompts"
                orientation="right"
                tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<ChartTooltip />} />
              <Legend wrapperStyle={{ fontSize: '10px', paddingTop: '8px' }} iconType="square" iconSize={8} />
              <Bar
                yAxisId="cost"
                dataKey="cost"
                name="Cost ($)"
                fill="hsl(var(--chart-1))"
                opacity={0.85}
                radius={[3, 3, 0, 0]}
                maxBarSize={40}
              />
              <Line
                yAxisId="prompts"
                dataKey="prompts"
                name="Prompts"
                stroke="hsl(var(--chart-2))"
                strokeWidth={2}
                dot={{ fill: 'hsl(var(--chart-2))', r: 3, strokeWidth: 0 }}
                activeDot={{ r: 5 }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}
