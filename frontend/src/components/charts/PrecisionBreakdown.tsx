import { motion } from 'framer-motion'
import { Ban, CircleCheck, Flag } from 'lucide-react'
import { formatPercent } from '@/lib/format'
import { CATEGORY_META } from '@/lib/meta'
import type { CategoryBreakdown } from '@/lib/types'

const SEGMENTS = [
  { key: 'accepted', label: 'Accepted', icon: CircleCheck, color: 'var(--rm-good)' },
  { key: 'dismissed', label: 'Dismissed', icon: Ban, color: 'var(--rm-fg-subtle)' },
  { key: 'false_positive', label: 'False positive', icon: Flag, color: 'var(--rm-warning)' },
] as const

/** Triage verdicts per category: the labelled data for measuring and tuning the reviewer's precision. */
export function PrecisionBreakdown({ categories }: { categories: CategoryBreakdown[] }) {
  const rows = categories
    .map((item) => ({ ...item, triaged: item.accepted + item.dismissed + item.false_positive }))
    .filter((item) => item.triaged > 0)
    .sort((a, b) => b.triaged - a.triaged)

  if (rows.length === 0) {
    return <p className="px-2 py-10 text-center text-sm text-fg-muted">Accept, dismiss or flag findings to start measuring precision.</p>
  }

  return (
    <div className="px-2">
      <ul className="mb-4 flex flex-wrap gap-x-4 gap-y-1.5" aria-label="Legend">
        {SEGMENTS.map((segment) => (
          <li key={segment.key} className="inline-flex items-center gap-1.5 text-xs text-fg-2">
            <segment.icon className="size-3.5" style={{ color: segment.color }} aria-hidden />
            {segment.label}
          </li>
        ))}
      </ul>
      <ul className="space-y-3.5">
        {rows.map((row, rowIndex) => (
          <li key={row.category}>
            <div className="mb-1.5 flex items-center justify-between gap-3 text-[13px]">
              <span className="inline-flex items-center gap-2 text-fg-2">
                <span aria-hidden className="size-2 rounded-[3px]" style={{ background: CATEGORY_META[row.category].color }} />
                {CATEGORY_META[row.category].label}
              </span>
              <span className="tabular text-fg-muted">
                <span className="font-semibold text-fg">{formatPercent(row.accepted / row.triaged)}</span> accepted of {row.triaged}
              </span>
            </div>
            <div className="flex h-2.5 gap-[2px] overflow-hidden rounded-full" aria-hidden>
              {SEGMENTS.map((segment) => {
                const share = row[segment.key] / row.triaged
                if (!share) return null
                return (
                  <motion.span
                    key={segment.key}
                    className="h-full origin-left first:rounded-l-full last:rounded-r-full"
                    style={{ width: `${share * 100}%`, background: segment.color }}
                    initial={{ scaleX: 0 }}
                    animate={{ scaleX: 1 }}
                    transition={{ duration: 0.6, delay: 0.1 + rowIndex * 0.05, ease: [0.22, 1, 0.36, 1] }}
                  />
                )
              })}
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
