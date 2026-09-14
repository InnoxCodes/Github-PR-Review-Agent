import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useChartTheme } from '@/lib/chartTheme'
import { shortDate } from '@/lib/format'
import { CATEGORIES, CATEGORY_META } from '@/lib/meta'
import type { Analytics, Category } from '@/lib/types'

type Week = Record<Category, number> & { label: string; reviews: number; total: number }

export function toWeeks(weekly: Analytics['weekly']): Week[] {
  return weekly.map((week) => ({
    ...week.counts,
    label: shortDate(`${week.week_start}T12:00:00`),
    reviews: week.reviews,
    total: Object.values(week.counts).reduce((sum, count) => sum + count, 0),
  }))
}

export function CategoryLegend() {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1.5" aria-label="Legend">
      {CATEGORIES.map((category) => (
        <li key={category} className="inline-flex items-center gap-1.5 text-xs text-fg-2">
          <span aria-hidden className="size-2.5 rounded-[3px]" style={{ background: CATEGORY_META[category].color }} />
          {CATEGORY_META[category].label}
        </li>
      ))}
    </ul>
  )
}

/** Stacked columns (categorical identity). Segments are separated by a 2px gap in the surface colour. */
export function WeeklyFindingsChart({ weekly }: { weekly: Analytics['weekly'] }) {
  const theme = useChartTheme()
  const data = toWeeks(weekly)

  return (
    <div className="h-[260px]" role="img" aria-label={`Findings per week by category over ${data.length} weeks.`}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: -16 }} barCategoryGap="30%">
          <CartesianGrid vertical={false} stroke={theme.grid} />
          <XAxis dataKey="label" tick={{ fill: theme.text, fontSize: 12 }} tickLine={false} axisLine={{ stroke: theme.axis }} minTickGap={16} />
          <YAxis allowDecimals={false} tick={{ fill: theme.text, fontSize: 12 }} tickLine={false} axisLine={false} width={40} />
          <Tooltip cursor={{ fill: theme.muted, fillOpacity: 0.4 }} content={<WeekTooltip />} />
          {CATEGORIES.map((category, index) => (
            <Bar
              key={category}
              dataKey={category}
              stackId="week"
              fill={theme.series[index]}
              maxBarSize={24}
              animationDuration={700}
              shape={(props: unknown) => <Segment {...(props as SegmentProps)} surface={theme.surface} category={category} />}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

interface SegmentProps {
  x?: number
  y?: number
  width?: number
  height?: number
  fill?: string
  payload?: Week
  surface: string
  category: Category
}

function Segment({ x = 0, y = 0, width = 0, height = 0, fill, payload, surface, category }: SegmentProps) {
  if (height <= 0 || !payload) return <g />
  const topCategory = [...CATEGORIES].reverse().find((item) => payload[item] > 0)
  const radius = topCategory === category ? Math.min(4, width / 2, height) : 0
  const path =
    `M${x},${y + height} L${x},${y + radius} Q${x},${y} ${x + radius},${y} ` +
    `L${x + width - radius},${y} Q${x + width},${y} ${x + width},${y + radius} L${x + width},${y + height} Z`
  return <path d={path} fill={fill} stroke={surface} strokeWidth={2} />
}

function WeekTooltip({ active, payload }: { active?: boolean; payload?: ReadonlyArray<{ payload: Week }> }) {
  if (!active || !payload?.length) return null
  const week = payload[0].payload
  return (
    <div className="min-w-44 rounded-lg border border-line-strong bg-raised px-3 py-2 shadow-pop">
      <p className="text-lg font-semibold leading-tight text-fg">
        {week.total}
        <span className="ml-1.5 text-xs font-medium text-fg-muted">findings</span>
      </p>
      <p className="text-xs text-fg-muted">
        Week of {week.label} · {week.reviews} review{week.reviews === 1 ? '' : 's'}
      </p>
      <ul className="mt-1.5 space-y-0.5">
        {CATEGORIES.filter((category) => week[category] > 0).map((category) => (
          <li key={category} className="flex items-center gap-2 text-xs">
            <span aria-hidden className="h-0.5 w-3 rounded-full" style={{ background: CATEGORY_META[category].color }} />
            <span className="tabular w-4 text-right font-semibold text-fg">{week[category]}</span>
            <span className="text-fg-2">{CATEGORY_META[category].label}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
