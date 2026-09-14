import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useChartTheme } from '@/lib/chartTheme'
import { CATEGORY_META } from '@/lib/meta'
import type { CategoryBreakdown } from '@/lib/types'

type Row = CategoryBreakdown & { label: string }

/** One series across nominal categories: a single hue, sorted by magnitude, value at each bar tip. */
export function CategoryBarChart({ categories }: { categories: CategoryBreakdown[] }) {
  const theme = useChartTheme()
  const data: Row[] = categories
    .map((item) => ({ ...item, label: CATEGORY_META[item.category].label }))
    .sort((a, b) => b.total - a.total)
  const top = data[0]

  return (
    <div
      style={{ height: data.length * 38 + 32 }}
      role="img"
      aria-label={top ? `Findings by category. Most common: ${top.label} with ${top.total}.` : 'No findings yet.'}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 40, bottom: 4, left: 4 }} barCategoryGap={12}>
          <CartesianGrid horizontal={false} stroke={theme.grid} />
          <XAxis type="number" allowDecimals={false} tick={{ fill: theme.text, fontSize: 12 }} tickLine={false} axisLine={false} />
          <YAxis
            type="category"
            dataKey="label"
            width={104}
            tick={{ fill: theme.fg2, fontSize: 13 }}
            tickLine={false}
            axisLine={{ stroke: theme.axis }}
          />
          <Tooltip cursor={{ fill: theme.muted, fillOpacity: 0.4 }} content={<CategoryTooltip />} />
          <Bar dataKey="total" fill={theme.series[0]} barSize={18} radius={[0, 4, 4, 0]} animationDuration={800}>
            <LabelList dataKey="total" position="right" fill={theme.fg2} fontSize={12} offset={8} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function CategoryTooltip({ active, payload }: { active?: boolean; payload?: ReadonlyArray<{ payload: Row }> }) {
  if (!active || !payload?.length) return null
  const row = payload[0].payload
  return (
    <div className="rounded-lg border border-line-strong bg-raised px-3 py-2 shadow-pop">
      <p className="text-lg font-semibold leading-tight text-fg">{row.total}</p>
      <p className="text-[13px] text-fg-2">{row.label}</p>
      <p className="mt-1 text-xs text-fg-muted">
        {row.critical} critical · {row.warning} warning · {row.info} info
      </p>
    </div>
  )
}
