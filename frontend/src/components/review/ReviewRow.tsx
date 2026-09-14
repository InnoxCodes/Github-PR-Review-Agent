import { motion } from 'framer-motion'
import { ChevronRight, CircleX, LoaderCircle } from 'lucide-react'
import { Link } from 'react-router'
import { Badge } from '@/components/ui/Badge'
import { cn } from '@/lib/cn'
import { formatNumber, relativeTime } from '@/lib/format'
import { SEVERITIES, SEVERITY_META, isActive } from '@/lib/meta'
import { riseIn } from '@/lib/motion'
import type { ReviewSummary } from '@/lib/types'
import { HealthGauge } from './HealthGauge'

export function ReviewRow({ review }: { review: ReviewSummary }) {
  const running = isActive(review.status)
  const failed = review.status === 'failed'

  return (
    <motion.li variants={riseIn}>
      <Link
        to={`/reviews/${review.id}`}
        className="group flex items-center gap-4 rounded-xl px-3 py-3 transition-colors duration-200 hover:bg-raised focus-visible:bg-raised"
      >
        <span className="grid size-12 shrink-0 place-items-center">
          {running ? (
            <span className="grid size-11 place-items-center rounded-full border border-accent/40 bg-accent-soft">
              <LoaderCircle className="spin-slow size-5 text-accent-text" aria-label="Review running" />
            </span>
          ) : failed ? (
            <span className="grid size-11 place-items-center rounded-full border border-critical/40 bg-critical-soft">
              <CircleX className="size-5 text-critical-text" aria-label="Review failed" />
            </span>
          ) : (
            <HealthGauge score={review.health_score} size={46} compact />
          )}
        </span>

        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2 font-mono text-xs text-fg-muted">
            <span className="truncate">
              {review.owner}/{review.repo}
            </span>
            <span className="shrink-0 text-fg-subtle">#{review.pr_number}</span>
            {review.is_sample && (
              <Badge tone="outline" className="h-5 px-1.5 font-sans">
                Sample
              </Badge>
            )}
          </span>
          <span className={cn('mt-0.5 block truncate text-[15px] font-medium', review.pr_title ? 'text-fg' : 'text-fg-muted')}>
            {review.pr_title ?? (running ? 'Fetching pull request…' : 'Untitled pull request')}
          </span>
          <span className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-fg-muted">
            {review.pr_author && <span>{review.pr_author}</span>}
            <span>{running ? (review.status_message ?? 'Queued') : failed ? 'Failed' : relativeTime(review.created_at)}</span>
            {!running && (
              <span className="tabular font-mono">
                <span className="text-diff-add-sign">+{formatNumber(review.additions)}</span>{' '}
                <span className="text-diff-del-sign">−{formatNumber(review.deletions)}</span>
              </span>
            )}
          </span>
        </span>

        <span className="hidden items-center gap-3 sm:flex">
          {SEVERITIES.map((severity) => {
            const count = review.issue_counts[severity]
            const Icon = SEVERITY_META[severity].icon
            return (
              <span
                key={severity}
                className={cn('inline-flex w-9 items-center gap-1 text-[13px] font-medium', count ? SEVERITY_META[severity].text : 'text-fg-subtle')}
              >
                <Icon className="size-3.5" aria-hidden />
                <span className="tabular">{count}</span>
                <span className="sr-only">{SEVERITY_META[severity].label}</span>
              </span>
            )
          })}
        </span>
        <ChevronRight className="size-4 shrink-0 text-fg-subtle transition-transform duration-200 group-hover:translate-x-0.5" aria-hidden />
      </Link>
    </motion.li>
  )
}
