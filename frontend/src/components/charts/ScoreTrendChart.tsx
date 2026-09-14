import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useChartTheme } from '@/lib/chartTheme'
import { shortDate } from '@/lib/format'
import { GRADE_META, gradeFor } from '@/lib/meta'
import type { Analytics } from '@/lib/types'

type Point = Analytics['score_trend'][number] & { index: number; day: string }

export function ScoreTrendChart({ points }: { points: Analytics['score_trend'] }) {
  const theme = useChartTheme()
  const data: Point[] = points.map((point, index) => ({ ...point, index, day: shortDate(point.date) }))
  const last = data.at(-1)
  const lastIndex = data.length - 1

  return (
    <div
      className="h-[260px]"
      role="img"
      aria-label={`Health score across ${data.length} reviews${last ? `, most recently ${last.score} for ${last.label}` : ''}.`}
    >
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 22, right: 28, bottom: 4, left: -8 }}>
          <defs>
            <linearGradient id="score-wash" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={theme.series[0]} stopOpacity={0.14} />
              <stop offset="100%" stopColor={theme.series[0]} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke={theme.grid} />
          <XAxis
            dataKey="index"
            type="number"
            domain={[0, Math.max(lastIndex, 1)]}
            ticks={data.length > 1 ? tickIndices(data.length) : [0]}
            tickFormatter={(index: number) => data[index]?.day ?? ''}
            tick={{ fill: theme.text, fontSize: 12 }}
            tickLine={false}
            axisLine={{ stroke: theme.axis }}
          />
          <YAxis domain={[0, 100]} ticks={[0, 50, 80, 100]} tick={{ fill: theme.text, fontSize: 12 }} tickLine={false} axisLine={false} width={36} />
          <Tooltip cursor={{ stroke: theme.axis, strokeWidth: 1 }} content={<ScoreTooltip />} />
          <Area
            type="monotone"
            dataKey="score"
            stroke={theme.series[0]}
            strokeWidth={2}
            fill="url(#score-wash)"
            activeDot={{ r: 5, stroke: theme.surface, strokeWidth: 2, fill: theme.series[0] }}
            dot={(props: { cx?: number; cy?: number; index?: number; payload?: Point }) =>
              props.index === lastIndex && props.cx !== undefined && props.cy !== undefined ? (
                <g key="last">
                  <circle cx={props.cx} cy={props.cy} r={5} fill={theme.series[0]} stroke={theme.surface} strokeWidth={2} />
                  <text x={props.cx} y={props.cy - 12} textAnchor="middle" fill={theme.fg} fontSize={12} fontWeight={600}>
                    {props.payload?.score}
                  </text>
                </g>
              ) : (
                <g key={props.index} />
              )
            }
            animationDuration={900}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

function tickIndices(length: number): number[] {
  const step = Math.max(1, Math.ceil(length / 6))
  const ticks = []
  for (let index = 0; index < length; index += step) ticks.push(index)
  if (ticks.at(-1) !== length - 1) ticks.push(length - 1)
  return ticks
}

function ScoreTooltip({ active, payload }: { active?: boolean; payload?: ReadonlyArray<{ payload: Point }> }) {
  if (!active || !payload?.length) return null
  const point = payload[0].payload
  const grade = gradeFor(point.score)
  return (
    <div className="max-w-64 rounded-lg border border-line-strong bg-raised px-3 py-2 shadow-pop">
      <p className="text-lg font-semibold leading-tight text-fg">
        {point.score}
        <span className="ml-1.5 text-xs font-medium text-fg-muted">{grade ? GRADE_META[grade].label : ''}</span>
      </p>
      <p className="mt-0.5 truncate text-[13px] text-fg-2">{point.title}</p>
      <p className="mt-0.5 font-mono text-xs text-fg-muted">
        {point.label} · {point.day}
      </p>
    </div>
  )
}
