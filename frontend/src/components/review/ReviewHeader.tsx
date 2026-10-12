import { ArrowUpRight, Clock, Coins, Cpu, FileCode2, GitBranch, GitMerge, GitPullRequest, Play, Sparkles, TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { GitHubMark } from '@/components/brand/Logo'
import { Avatar } from '@/components/ui/Avatar'
import { Badge } from '@/components/ui/Badge'
import { Button, buttonClasses } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Tooltip } from '@/components/ui/Tooltip'
import { cn } from '@/lib/cn'
import { formatCompact, formatCost, formatDuration, formatNumber, plural } from '@/lib/format'
import { GRADE_META, SEVERITIES, SEVERITY_META } from '@/lib/meta'
import type { ReviewDetail } from '@/lib/types'
import { HealthGauge } from './HealthGauge'

export function ReviewHeader({ review, onReplay }: { review: ReviewDetail; onReplay: () => void }) {
  const grade = review.grade ? GRADE_META[review.grade] : null
  const GradeIcon = grade?.icon
  const delta =
    review.health_score !== null && review.initial_health_score !== null ? review.health_score - review.initial_health_score : 0
  const totalInput = review.tokens.input_tokens + review.tokens.cache_read_tokens + review.tokens.cache_creation_tokens
  const cacheShare = totalInput ? review.tokens.cache_read_tokens / totalInput : 0
  const reviewedFiles = review.files.filter((file) => file.state === 'done').length

  return (
    <Card className="relative overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute -right-28 -top-32 size-80 rounded-full opacity-30 blur-3xl"
        style={{ background: `radial-gradient(circle, ${grade?.color ?? 'transparent'}, transparent 70%)` }}
      />
      <div className="relative flex flex-col gap-6 p-5 sm:p-6 lg:flex-row lg:items-center">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 text-[13px]">
            <Link
              to={`/reviews?repository=${encodeURIComponent(`${review.owner}/${review.repo}`)}`}
              className="font-mono text-fg-muted transition-colors hover:text-fg"
            >
              {review.owner}/<span className="text-fg-2">{review.repo}</span>
            </Link>
            <span className="font-mono text-fg-subtle">#{review.pr_number}</span>
            {review.pr_merged ? (
              <Badge tone="info">
                <GitMerge aria-hidden /> Merged
              </Badge>
            ) : (
              <Badge tone="accent">
                <GitPullRequest aria-hidden /> {review.pr_draft ? 'Draft' : 'Open'}
              </Badge>
            )}
            {review.is_sample && (
              <Tooltip content="Hand-written sample data, not model output">
                <Badge tone="outline" tabIndex={0}>
                  Sample
                </Badge>
              </Tooltip>
            )}
            <div className="ml-auto flex items-center gap-2">
              <Button size="sm" variant="ghost" onClick={onReplay}>
                <Play className="size-3.5" aria-hidden /> Replay stream
              </Button>
              {review.is_sample ? (
                <Button size="sm" variant="outline" disabled title="Sample repositories aren't on GitHub">
                  <GitHubMark className="size-3.5" /> GitHub
                </Button>
              ) : (
                <a href={review.pr_url} target="_blank" rel="noreferrer" className={buttonClasses('outline', 'sm')}>
                  <GitHubMark className="size-3.5" /> GitHub <ArrowUpRight className="size-3.5" aria-hidden />
                </a>
              )}
            </div>
          </div>

          <h1 className="mt-3 font-sans text-2xl font-semibold tracking-tight text-fg sm:text-[28px] sm:leading-tight">
            {review.pr_title}
          </h1>

          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-[13px] text-fg-muted">
            {review.pr_author && (
              <span className="inline-flex items-center gap-2">
                <Avatar name={review.pr_author} src={review.pr_author_avatar} size={20} />
                <span className="font-medium text-fg-2">{review.pr_author}</span>
              </span>
            )}
            {review.head_ref && (
              <span className="inline-flex min-w-0 items-center gap-1.5 font-mono text-xs">
                <GitBranch className="size-3.5 shrink-0" aria-hidden />
                <span className="truncate rounded bg-muted px-1.5 py-0.5 text-fg-2">{review.head_ref}</span>
                <span aria-label="into">→</span>
                <span className="rounded bg-muted px-1.5 py-0.5 text-fg-2">{review.base_ref}</span>
              </span>
            )}
            <span className="tabular font-mono text-xs">
              <span className="text-diff-add-sign">+{formatNumber(review.additions)}</span>{' '}
              <span className="text-diff-del-sign">−{formatNumber(review.deletions)}</span>
            </span>
            <span>{plural(review.changed_files, 'file')}</span>
            <span>{plural(review.commits, 'commit')}</span>
          </div>

          {review.summary && (
            <p className="mt-4 flex items-start gap-2 text-[15px] leading-relaxed text-fg-2">
              <Sparkles className="mt-1 size-4 shrink-0 text-accent-text" aria-hidden />
              {review.summary}
            </p>
          )}
        </div>

        <div className="flex items-center gap-5 lg:border-l lg:border-line lg:pl-7">
          <HealthGauge score={review.health_score} size={136} />
          <div className="min-w-[10rem]">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-fg-muted">PR health</p>
            {grade && GradeIcon && (
              <p className={cn('mt-1.5 inline-flex items-center gap-1.5 text-[15px] font-semibold', grade.text)}>
                <GradeIcon className="size-4" aria-hidden /> {grade.label}
              </p>
            )}
            {delta !== 0 && (
              <p className="mt-1 text-xs text-fg-muted">
                {delta > 0 ? '+' : ''}
                {delta} since triage (was {review.initial_health_score})
              </p>
            )}
            <div className="mt-3 flex flex-wrap gap-2">
              {SEVERITIES.map((severity) => {
                const Icon = SEVERITY_META[severity].icon
                return (
                  <span key={severity} className={cn('inline-flex items-center gap-1 text-[13px] font-medium', SEVERITY_META[severity].text)}>
                    <Icon className="size-3.5" aria-hidden />
                    <span className="tabular">{review.issue_counts[severity]}</span>
                    <span className="sr-only">{SEVERITY_META[severity].label}</span>
                  </span>
                )
              })}
            </div>
          </div>
        </div>
      </div>

      <dl className="relative grid grid-cols-2 gap-px border-t border-line bg-line sm:grid-cols-3 xl:grid-cols-6">
        <Stat label="Open findings" icon={<TriangleAlert />} value={`${review.open_issues} of ${review.issues_total}`} />
        <Stat label="Files reviewed" icon={<FileCode2 />} value={`${reviewedFiles} of ${review.files.length}`} />
        <Stat label="Model" icon={<Cpu />} value={review.model ?? '-'} mono />
        <Stat label="Review time" icon={<Clock />} value={formatDuration(review.duration_ms)} />
        <Stat
          label="Tokens"
          icon={<Sparkles />}
          value={formatCompact(totalInput + review.tokens.output_tokens)}
          hint={cacheShare > 0 ? `${Math.round(cacheShare * 100)}% of input cached` : undefined}
        />
        <Stat
          label="LLM cost"
          icon={<Coins />}
          value={formatCost(review.cost_usd)}
          hint={`${plural(review.llm_calls, 'call')}${review.invalid_outputs ? ` · ${review.invalid_outputs} retried` : ''}`}
        />
      </dl>
    </Card>
  )
}

function Stat({ label, value, icon, hint, mono = false }: { label: string; value: string; icon: ReactNode; hint?: string; mono?: boolean }) {
  return (
    <div className="bg-surface px-5 py-3.5">
      <dt className="flex items-center gap-1.5 text-xs text-fg-muted [&_svg]:size-3.5">
        {icon}
        {label}
      </dt>
      <dd className={cn('mt-1 truncate text-[15px] font-semibold text-fg', mono && 'font-mono text-[13px]')}>{value}</dd>
      {hint && <dd className="mt-0.5 truncate text-xs text-fg-muted">{hint}</dd>}
    </div>
  )
}
