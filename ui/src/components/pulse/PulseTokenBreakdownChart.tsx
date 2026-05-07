import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'
import { fmtTokens } from '@/types/pulse'

const COLORS = [
  'hsl(var(--chart-1))',
  'hsl(var(--chart-2))',
  'hsl(var(--chart-3))',
  'hsl(var(--chart-4))',
]

interface PulseTokenBreakdownChartProps {
  input: number
  output: number
  cacheRead: number
  cacheCreation: number
}

export function PulseTokenBreakdownChart({ input, output, cacheRead, cacheCreation }: PulseTokenBreakdownChartProps) {
  const data = [
    { name: 'Input', value: input || 0 },
    { name: 'Output', value: output || 0 },
    { name: 'Cache Read', value: cacheRead || 0 },
    { name: 'Cache Creation', value: cacheCreation || 0 },
  ].filter(d => d.value > 0)

  if (data.length === 0) return null

  return (
    <div className="h-[160px]">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={35}
            outerRadius={60}
            paddingAngle={2}
            dataKey="value"
          >
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              background: 'hsl(var(--card))',
              border: '1px solid hsl(var(--border))',
              borderRadius: '8px',
              fontSize: '11px',
              color: 'hsl(var(--card-foreground))',
            }}
            formatter={(value: number) => fmtTokens(value)}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}
