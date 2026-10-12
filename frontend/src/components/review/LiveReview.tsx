import { AnimatePresence, motion } from 'framer-motion'
import { Check, CircleX, Coins, Cpu, RefreshCw, Sparkles, Timer, WifiOff } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { Avatar } from '@/components/ui/Avatar'
import { AnimatedNumber } from '@/components/ui/AnimatedNumber'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { cn } from '@/lib/cn'
import { basename, dirname, formatCompact, formatCost, plural } from '@/lib/format'
import { useElapsedSeconds } from '@/lib/hooks'
import { SEVERITIES, SEVERITY_META, SKIP_REASON_LABEL } from '@/lib/meta'
import { easeOut, spring } from '@/lib/motion'
import { useReviewStream, type StreamFile, type StreamState } from '@/lib/stream'
import type { Issue, ReviewStatus, ReviewSummary } from '@/lib/types'
import { CategoryTag } from './CategoryTag'
import { FileStateIcon } from './FileStateIcon'
import { HealthGauge } from './HealthGauge'

interface LiveReviewProps {
  reviewId: string
  summary: ReviewSummary
  replay: boolean
  onFinished: (outcome: 'completed' | 'failed', state: StreamState) => void
}

const STAGES: { status: ReviewStatus; label: string }[] = [
  { status: 'queued', label: 'Queued' },
  { status: 'fetching', label: 'Fetching diff' },
  { status: 'reviewing', label: 'AI review' },
  { status: 'completed', label: 'Scored' },
]

export function LiveReview({ reviewId, summary, replay, onFinished }: LiveReviewProps) {
  const finishTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const stream = useReviewStream(reviewId, {
    enabled: true,
    replay,
    onTerminal: (outcome, state) => {
      // Hold the finished state briefly so the score landing is visible before the dashboard takes over.
      finishTimer.current = setTimeout(() => onFinished(outcome, state), outcome === 'completed' ? 1500 : 300)
    },
  })

  useEffect(() => () => clearTimeout(finishTimer.current), [])

  const review = stream.review ?? summary
  const status = stream.status ?? summary.status
  const running = stream.terminal === null
  const elapsed = useElapsedSeconds(replay ? null : summary.created_at, running)
  const reviewable = stream.files.filter((file) => file.state !== 'skipped')
  const skipped = stream.files.filter((file) => file.state === 'skipped')
  const progress = stream.filesTotal ? stream.filesDone / stream.filesTotal : 0
  const stageIndex = stream.terminal === 'completed' ? 3 : Math.max(0, STAGES.findIndex((stage) => stage.status === status))

  return (
    <div className="mx-auto max-w-[1400px] space-y-5 px-4 py-6 sm:px-6">
      <p className="sr-only" aria-live="polite">
        {stream.terminal === 'completed'
          ? 'Review complete.'
          : stream.filesTotal
            ? `Reviewed ${stream.filesDone} of ${stream.filesTotal} files.`
            : (stream.message ?? 'Starting review.')}
      </p>

      <Card className="relative overflow-hidden">
        <div aria-hidden className="absolute inset-x-0 top-0 h-px overflow-hidden">
          <motion.div
            className="h-full bg-accent"
            initial={{ scaleX: 0 }}
            animate={{ scaleX: stream.terminal === 'completed' ? 1 : Math.max(0.04, progress) }}
            transition={easeOut}
            style={{ transformOrigin: 'left' }}
          />
        </div>
        <div className="flex flex-col gap-6 p-5 sm:p-6 lg:flex-row lg:items-center">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2 text-[13px]">
              <span className="font-mono text-fg-muted">
                {review.owner}/<span className="text-fg-2">{review.repo}</span>
              </span>
              <span className="font-mono text-fg-subtle">#{review.pr_number}</span>
              {replay ? (
                <Badge tone="info">
                  <RefreshCw aria-hidden /> Replaying stored stream
                </Badge>
              ) : (
                running && (
                  <Badge tone="accent">
                    <span className="relative flex size-2">
                      <span className="absolute inline-flex size-full animate-ping rounded-full bg-accent opacity-60" />
                      <span className="relative inline-flex size-2 rounded-full bg-accent" />
                    </span>
                    Live
                  </Badge>
                )
              )}
              {stream.connection === 'connecting' && stream.lastEventId > 0 && (
                <Badge tone="warning">
                  <WifiOff aria-hidden /> Reconnecting…
                </Badge>
              )}
            </div>
            {review.pr_title ? (
              <h1 className="mt-3 font-sans text-2xl font-semibold tracking-tight text-fg sm:text-[28px]">{review.pr_title}</h1>
            ) : (
              <Skeleton className="mt-3 h-8 w-2/3" />
            )}
            <div className="mt-3 flex min-h-5 flex-wrap items-center gap-x-4 gap-y-2 text-[13px] text-fg-muted">
              {review.pr_author ? (
                <span className="inline-flex items-center gap-2">
                  <Avatar name={review.pr_author} src={review.pr_author_avatar} size={20} />
                  <span className="font-medium text-fg-2">{review.pr_author}</span>
                </span>
              ) : (
                <Skeleton className="h-4 w-40" />
              )}
              <span className="inline-flex items-center gap-1.5">
                <Cpu className="size-3.5" aria-hidden />
                <span className="font-mono text-xs">{stream.model ?? summary.model ?? '-'}</span>
              </span>
              {!replay && (
                <span className="tabular inline-flex items-center gap-1.5">
                  <Timer className="size-3.5" aria-hidden /> {formatElapsed(elapsed)}
                </span>
              )}
              <span className="tabular inline-flex items-center gap-1.5">
                <Sparkles className="size-3.5" aria-hidden />
                <AnimatedNumber value={stream.tokens} format={(v) => `${formatCompact(Math.round(v))} tokens`} />
              </span>
              <span className="tabular inline-flex items-center gap-1.5">
                <Coins className="size-3.5" aria-hidden />
                <AnimatedNumber value={stream.costUsd ?? 0} format={(v) => formatCost(v)} />
              </span>
            </div>
            <StageStepper activeIndex={stageIndex} failed={stream.terminal === 'failed'} />
            <p className="mt-3 min-h-5 text-[13px] text-fg-muted">{stream.terminal === 'completed' ? 'Review complete, opening the dashboard…' : stream.message}</p>
          </div>

          <div className="flex items-center gap-5 lg:border-l lg:border-line lg:pl-7">
            <AnimatePresence mode="wait" initial={false}>
              {stream.terminal === 'completed' && stream.review ? (
                <motion.div key="score" initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={spring}>
                  <HealthGauge score={stream.review.health_score} size={132} />
                </motion.div>
              ) : (
                <motion.div key="progress" exit={{ opacity: 0, scale: 0.9 }}>
                  <ProgressRing value={progress} done={stream.filesDone} total={stream.filesTotal} />
                </motion.div>
              )}
            </AnimatePresence>
            <div className="min-w-[9rem] space-y-1.5">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-fg-muted">Findings so far</p>
              {SEVERITIES.map((severity) => {
                const meta = SEVERITY_META[severity]
                const Icon = meta.icon
                const count = stream.issues.filter((issue) => issue.severity === severity).length
                return (
                  <div key={severity} className={cn('flex items-center gap-2 text-sm font-medium', meta.text)}>
                    <Icon className="size-4" aria-hidden />
                    <span className="w-16">{meta.label}</span>
                    <AnimatedNumber value={count} className="tabular text-fg" duration={0.4} />
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </Card>

      {stream.terminal === 'failed' && (
        <Card className="flex items-start gap-3 border-critical/40 p-5">
          <CircleX className="mt-0.5 size-5 shrink-0 text-critical-text" aria-hidden />
          <div>
            <p className="font-semibold text-fg">The review failed</p>
            <p className="mt-1 text-sm text-fg-muted">{stream.error}</p>
          </div>
        </Card>
      )}

      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <Card>
          <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
            <h2 className="font-mono text-[15px] font-semibold text-fg">Files</h2>
            <span className="tabular text-[13px] text-fg-muted">
              {stream.filesDone} / {stream.filesTotal || '…'} reviewed
            </span>
          </div>
          {stream.files.length === 0 ? (
            <div className="space-y-3 p-5" aria-busy="true">
              {Array.from({ length: 5 }, (_, index) => (
                <div key={index} className="flex items-center gap-3">
                  <Skeleton className="size-5 rounded-full" />
                  <Skeleton className="h-4 flex-1" />
                  <Skeleton className="h-4 w-12" />
                </div>
              ))}
            </div>
          ) : (
            <ul className="divide-y divide-line">
              {reviewable.map((file) => (
                <FileRow key={file.id} file={file} />
              ))}
              {skipped.map((file) => (
                <FileRow key={file.id} file={file} />
              ))}
            </ul>
          )}
        </Card>

        <Card className="min-h-[24rem]">
          <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
            <h2 className="font-mono text-[15px] font-semibold text-fg">Live findings</h2>
            <span className="tabular text-[13px] text-fg-muted">{plural(stream.issues.length, 'finding')}</span>
          </div>
          <div className="space-y-2.5 p-4">
            <AnimatePresence initial={false}>
              {stream.retries.map((retry, index) => (
                <motion.div
                  key={`retry-${index}`}
                  layout="position"
                  initial={{ opacity: 0, y: -8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex items-start gap-2.5 rounded-lg border border-warning/30 bg-warning-soft px-3 py-2 text-[13px] text-warning-text"
                >
                  <RefreshCw className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                  <span>
                    Output for <span className="font-mono">{basename(retry.filename)}</span> failed validation, retried with the error
                    fed back to the model.
                  </span>
                </motion.div>
              ))}
              {stream.issues.map((issue) => (
                <FeedItem key={issue.id} issue={issue} />
              ))}
            </AnimatePresence>
            {stream.issues.length === 0 && (
              <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
                <div className="scan-sweep relative grid size-14 place-items-center overflow-hidden rounded-2xl border border-line-strong bg-raised">
                  {stream.terminal === 'completed' ? (
                    <Check className="size-6 text-good-text" aria-hidden />
                  ) : (
                    <Sparkles className="size-6 text-accent-text" aria-hidden />
                  )}
                </div>
                <p className="text-sm text-fg-muted">
                  {stream.terminal === 'completed' ? 'No issues found in the reviewed files.' : 'Findings appear here the moment each file is analysed.'}
                </p>
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  )
}

function FileRow({ file }: { file: StreamFile }) {
  return (
    <li className={cn('relative flex items-center gap-3 px-5 py-3', file.state === 'reviewing' && 'scan-sweep')}>
      <FileStateIcon state={file.state} />
      <div className="min-w-0 flex-1">
        <p className={cn('truncate font-mono text-[13px]', file.state === 'skipped' ? 'text-fg-subtle' : 'text-fg')}>
          <span className="text-fg-muted">{dirname(file.filename)}</span>
          {basename(file.filename)}
        </p>
        <p className="mt-0.5 truncate text-xs text-fg-muted">
          {file.state === 'skipped'
            ? `Skipped · ${SKIP_REASON_LABEL[file.skip_reason ?? ''] ?? file.skip_reason}`
            : file.state === 'failed'
              ? (file.error ?? 'Failed')
              : file.state === 'reviewing'
                ? `Analysing${file.chunks > 1 ? ` · ${file.chunks} chunks` : ''}…`
                : file.state === 'done'
                  ? (file.summary ?? 'Reviewed')
                  : 'Waiting'}
        </p>
      </div>
      {file.retries > 0 && (
        <Badge tone="warning" className="hidden sm:inline-flex">
          <RefreshCw aria-hidden /> retried
        </Badge>
      )}
      <AnimatePresence>
        {file.issue_count > 0 && (
          <motion.span
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: 'spring', stiffness: 600, damping: 20 }}
            className="tabular grid h-6 min-w-6 place-items-center rounded-full bg-muted px-2 text-xs font-semibold text-fg"
            aria-label={plural(file.issue_count, 'finding')}
          >
            {file.issue_count}
          </motion.span>
        )}
      </AnimatePresence>
    </li>
  )
}

function FeedItem({ issue }: { issue: Issue }) {
  const meta = SEVERITY_META[issue.severity]
  const Icon = meta.icon
  return (
    <motion.div
      layout="position"
      initial={{ opacity: 0, y: -14, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={spring}
      className={cn('flex items-start gap-3 rounded-xl border border-line border-l-[3px] bg-surface px-3.5 py-3', meta.border)}
    >
      <span className={cn('mt-0.5 grid size-7 shrink-0 place-items-center rounded-lg', meta.soft, meta.text)}>
        <Icon className="size-4" aria-label={meta.label} />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-fg">{issue.title}</p>
        <p className="mt-0.5 truncate font-mono text-xs text-fg-muted">
          {issue.filename}:{issue.line_number}
        </p>
      </div>
      <CategoryTag category={issue.category} className="hidden shrink-0 sm:inline-flex" />
    </motion.div>
  )
}

function StageStepper({ activeIndex, failed }: { activeIndex: number; failed: boolean }) {
  return (
    <ol className="mt-5 flex items-center gap-2" aria-label="Review progress">
      {STAGES.map((stage, index) => {
        const done = index < activeIndex || (index === activeIndex && index === STAGES.length - 1)
        const active = index === activeIndex && !done
        return (
          <li key={stage.status} className="flex flex-1 items-center gap-2 last:flex-none" aria-current={active ? 'step' : undefined}>
            <span
              className={cn(
                'relative grid size-6 shrink-0 place-items-center rounded-full border text-xs font-semibold transition-colors duration-300',
                done && 'border-accent bg-accent text-accent-fg',
                active && !failed && 'border-accent text-accent-text',
                active && failed && 'border-critical text-critical-text',
                !done && !active && 'border-line-strong text-fg-subtle',
              )}
            >
              {done ? <Check className="size-3.5" strokeWidth={3} aria-hidden /> : index + 1}
              {active && !failed && <span aria-hidden className="absolute inset-0 animate-ping rounded-full border border-accent opacity-40" />}
            </span>
            <span className={cn('whitespace-nowrap text-xs font-medium', done || active ? 'text-fg-2' : 'text-fg-subtle')}>{stage.label}</span>
            {index < STAGES.length - 1 && (
              <span aria-hidden className="relative hidden h-px flex-1 overflow-hidden bg-line-strong sm:block">
                <motion.span
                  className="absolute inset-0 bg-accent"
                  initial={false}
                  animate={{ scaleX: index < activeIndex ? 1 : 0 }}
                  transition={easeOut}
                  style={{ transformOrigin: 'left' }}
                />
              </span>
            )}
          </li>
        )
      })}
    </ol>
  )
}

function ProgressRing({ value, done, total }: { value: number; done: number; total: number }) {
  const size = 132
  const stroke = 9
  const radius = (size - stroke) / 2 - 1
  const circumference = 2 * Math.PI * radius
  return (
    <div className="relative" style={{ width: size, height: size }} role="progressbar" aria-valuemin={0} aria-valuemax={total || 1} aria-valuenow={done} aria-label="Files reviewed">
      <svg viewBox={`0 0 ${size} ${size}`} className="-rotate-90" width={size} height={size} aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--rm-line-strong)" strokeWidth={stroke} />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--rm-accent)"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: circumference * (1 - value) }}
          transition={easeOut}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">
        <div>
          <p className="tabular text-[28px] font-semibold leading-none text-fg">
            {done}
            <span className="text-base text-fg-muted">/{total || '–'}</span>
          </p>
          <p className="mt-1 text-xs text-fg-muted">files</p>
        </div>
      </div>
    </div>
  )
}

function formatElapsed(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
  return `${minutes}:${String(seconds % 60).padStart(2, '0')}`
}
