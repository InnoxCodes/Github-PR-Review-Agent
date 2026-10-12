import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import { CircleX, RotateCcw, SearchX } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { toast } from 'sonner'
import { DiffViewer } from '@/components/review/DiffViewer'
import { IssuePanel } from '@/components/review/IssuePanel'
import { DEFAULT_FILTERS, applyIssueFilters, matchesStatus, type IssueFilters } from '@/components/review/issueFilters'
import { LiveReview } from '@/components/review/LiveReview'
import { ReviewHeader } from '@/components/review/ReviewHeader'
import { Button, buttonClasses } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { Skeleton } from '@/components/ui/Skeleton'
import { api, ApiError, queryKeys } from '@/lib/api'
import { plural } from '@/lib/format'
import { useHotkeys } from '@/lib/hotkeys'
import { ISSUE_STATUS_META, isActive } from '@/lib/meta'
import { easeOut, exitFast } from '@/lib/motion'
import type { StreamState } from '@/lib/stream'
import type { Issue, IssueStatus, ReviewDetail } from '@/lib/types'

export default function ReviewPage() {
  const { reviewId = '' } = useParams()
  return <ReviewPageContent key={reviewId} reviewId={reviewId} />
}

function ReviewPageContent({ reviewId }: { reviewId: string }) {
  const queryClient = useQueryClient()
  const [replayKey, setReplayKey] = useState(0)
  const query = useQuery({ queryKey: queryKeys.review(reviewId), queryFn: () => api.getReview(reviewId) })

  if (query.isLoading) return <DashboardSkeleton />
  if (query.isError || !query.data) {
    const notFound = query.error instanceof ApiError && query.error.status === 404
    return (
      <div className="mx-auto max-w-3xl px-5 py-16">
        <Card>
          <EmptyState
            icon={SearchX}
            title={notFound ? 'Review not found' : "Couldn't load this review"}
            description={notFound ? 'It may have been deleted.' : (query.error?.message ?? 'Unknown error')}
            action={
              <Link to="/reviews" className={buttonClasses('secondary', 'sm')}>
                All reviews
              </Link>
            }
          />
        </Card>
      </div>
    )
  }

  const review = query.data
  const replaying = replayKey > 0
  const live = isActive(review.status) || replaying

  function handleFinished(outcome: 'completed' | 'failed', state: StreamState) {
    setReplayKey(0)
    queryClient.invalidateQueries({ queryKey: queryKeys.review(reviewId) })
    queryClient.invalidateQueries({ queryKey: queryKeys.allReviews })
    queryClient.invalidateQueries({ queryKey: queryKeys.allAnalytics })
    queryClient.invalidateQueries({ queryKey: queryKeys.repos })
    if (replaying) return
    if (outcome === 'completed') {
      toast.success('Review complete', {
        description: `${plural(state.review?.issues_total ?? state.issues.length, 'finding')} · health score ${state.review?.health_score ?? '-'}`,
      })
    } else {
      toast.error('Review failed', { description: state.error ?? undefined })
    }
  }

  return (
    <AnimatePresence mode="wait">
      {live ? (
        <motion.div key={`live-${replayKey}`} exit={{ opacity: 0, transition: exitFast }}>
          <LiveReview reviewId={reviewId} summary={review} replay={replaying} onFinished={handleFinished} />
        </motion.div>
      ) : review.status === 'failed' ? (
        <motion.div key="failed" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={easeOut}>
          <FailedReview review={review} />
        </motion.div>
      ) : (
        <motion.div key="dashboard" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={easeOut}>
          <ReviewDashboard review={review} onReplay={() => setReplayKey((key) => key + 1)} />
        </motion.div>
      )}
    </AnimatePresence>
  )
}

type SelectionSource = 'diff' | 'panel' | 'keyboard'

interface IssueMutation {
  issueId: string
  status: IssueStatus
  previous: IssueStatus
}

function ReviewDashboard({ review, onReplay }: { review: ReviewDetail; onReplay: () => void }) {
  const queryClient = useQueryClient()
  const key = queryKeys.review(review.id)
  const [filters, setFilters] = useState<IssueFilters>(DEFAULT_FILTERS)
  // Where a selection came from decides which side scrolls: clicking in the diff shouldn't yank
  // the diff, clicking a card shouldn't jump the list, and the keyboard moves both into view.
  const [selection, setSelection] = useState<{ id: string | null; source: SelectionSource }>({ id: null, source: 'keyboard' })
  const selectedId = selection.id
  const select = (id: string | null, source: SelectionSource) => setSelection({ id, source })
  const [lingering, setLingering] = useState<ReadonlySet<string>>(() => new Set())

  const filePosition = useMemo(() => new Map(review.files.map((file, index) => [file.id, index])), [review.files])
  const languages = useMemo(() => new Map(review.files.map((file) => [file.id, file.language])), [review.files])
  const visible = useMemo(
    () => applyIssueFilters(review.issues, filters, filePosition, lingering),
    [review.issues, filters, filePosition, lingering],
  )
  const selectable = visible.filter((issue) => !lingering.has(issue.id))
  const selected = visible.find((issue) => issue.id === selectedId) ?? null

  const mutation = useMutation({
    mutationFn: ({ issueId, status }: IssueMutation) => api.updateIssue(review.id, issueId, status),
    onMutate: async ({ issueId, status }) => {
      await queryClient.cancelQueries({ queryKey: key })
      queryClient.setQueryData<ReviewDetail>(key, (old) =>
        old
          ? {
              ...old,
              issues: old.issues.map((issue) =>
                issue.id === issueId ? { ...issue, status, resolved_at: status === 'open' ? null : new Date().toISOString() } : issue,
              ),
            }
          : old,
      )
    },
    onSuccess: (result) => {
      queryClient.setQueryData<ReviewDetail>(key, (old) =>
        old
          ? {
              ...old,
              health_score: result.health_score,
              grade: result.grade,
              issue_counts: result.issue_counts,
              open_issues: result.open_issues,
              issues: old.issues.map((issue) => (issue.id === result.issue.id ? result.issue : issue)),
            }
          : old,
      )
      queryClient.invalidateQueries({ queryKey: queryKeys.allReviews })
      queryClient.invalidateQueries({ queryKey: queryKeys.allAnalytics })
      queryClient.invalidateQueries({ queryKey: queryKeys.repos })
    },
    onError: (error, { issueId, previous }) => {
      queryClient.setQueryData<ReviewDetail>(key, (old) =>
        old ? { ...old, issues: old.issues.map((issue) => (issue.id === issueId ? { ...issue, status: previous } : issue)) } : old,
      )
      toast.error("Couldn't update the finding", { description: error.message })
    },
  })

  function linger(issueId: string) {
    // Keep a triaged card on screen long enough to see its confirmation before it leaves the list.
    setLingering((current) => new Set(current).add(issueId))
    setTimeout(() => {
      setLingering((current) => {
        const next = new Set(current)
        next.delete(issueId)
        return next
      })
    }, 650)
  }

  function setStatus(issue: Issue, status: IssueStatus) {
    if (issue.status === status) return
    const previous = issue.status
    if (!matchesStatus(status, filters.status)) {
      linger(issue.id)
      if (selectedId === issue.id) {
        const index = selectable.findIndex((item) => item.id === issue.id)
        const next = selectable[index + 1] ?? selectable[index - 1]
        select(next ? next.id : null, 'keyboard')
      }
    }
    mutation.mutate({ issueId: issue.id, status, previous })
    if (status !== 'open') {
      toast(`${ISSUE_STATUS_META[status].label}: ${issue.title}`, {
        action: { label: 'Undo', onClick: () => mutation.mutate({ issueId: issue.id, status: previous, previous: status }) },
      })
    }
  }

  function move(delta: number) {
    if (selectable.length === 0) return
    const index = selectable.findIndex((issue) => issue.id === selectedId)
    const next = index === -1 ? (delta > 0 ? 0 : selectable.length - 1) : Math.min(selectable.length - 1, Math.max(0, index + delta))
    select(selectable[next].id, 'keyboard')
  }

  useHotkeys({
    j: () => move(1),
    k: () => move(-1),
    a: () => selected && setStatus(selected, 'accepted'),
    d: () => selected && setStatus(selected, 'dismissed'),
    f: () => selected && setStatus(selected, 'false_positive'),
    u: () => selected && setStatus(selected, 'open'),
    c: () => {
      if (!selected?.suggested_fix) return
      navigator.clipboard
        .writeText(selected.suggested_fix)
        .then(() => toast.success('Suggested fix copied'))
        .catch(() => toast.error('Clipboard access was blocked by the browser.'))
    },
    Escape: () => select(null, 'keyboard'),
  })

  const reviewableFiles = review.files.filter((file) => file.state !== 'skipped').length

  return (
    <div className="mx-auto max-w-[1600px] space-y-5 px-4 py-6 sm:px-6">
      <ReviewHeader review={review} onReplay={onReplay} />

      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(360px,430px)]">
        <section aria-label="Changed files" className="order-2 min-w-0 space-y-3 lg:order-1">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="font-mono text-[15px] font-semibold text-fg">
              Changes{' '}
              <span className="font-sans text-[13px] font-normal text-fg-muted">
                {plural(review.files.length, 'file')} · {reviewableFiles} reviewed
              </span>
            </h2>
            <label htmlFor="file-jump" className="sr-only">
              Jump to file
            </label>
            <select
              id="file-jump"
              defaultValue=""
              onChange={(event) => {
                document.getElementById(`file-${event.target.value}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
                event.target.value = ''
              }}
              className="h-8 max-w-full cursor-pointer rounded-lg border border-line bg-surface px-2.5 font-mono text-xs text-fg-2 transition-colors hover:border-line-strong sm:max-w-72"
            >
              <option value="" disabled>
                Jump to file…
              </option>
              {review.files.map((file) => (
                <option key={file.id} value={file.id}>
                  {file.filename}
                  {file.issue_count ? ` (${file.issue_count})` : ''}
                </option>
              ))}
            </select>
          </div>
          <DiffViewer
            reviewId={review.id}
            files={review.files}
            issues={visible}
            selectedIssueId={selectedId}
            onSelectIssue={(id) => select(id, 'diff')}
            autoScroll={selection.source !== 'diff'}
          />
        </section>

        <IssuePanel
          className="order-1 lg:sticky lg:top-4 lg:order-2 lg:max-h-[calc(100dvh-2rem)]"
          issues={review.issues}
          visible={visible}
          filters={filters}
          onFiltersChange={setFilters}
          selectedId={selectedId}
          onSelect={(id) => select(id, 'panel')}
          autoScroll={selection.source !== 'panel'}
          onStatus={setStatus}
          languageFor={(fileId) => languages.get(fileId) ?? 'text'}
        />
      </div>
    </div>
  )
}

function FailedReview({ review }: { review: ReviewDetail }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const retry = useMutation({
    mutationFn: () => api.createReview(review.pr_url),
    onSuccess: (next) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.allReviews })
      navigate(`/reviews/${next.id}`)
    },
    onError: (error) => toast.error("Couldn't restart the review", { description: error.message }),
  })

  return (
    <div className="mx-auto max-w-3xl px-5 py-12">
      <Card className="overflow-hidden">
        <div className="flex items-start gap-4 p-6">
          <span className="grid size-11 shrink-0 place-items-center rounded-xl border border-critical/30 bg-critical-soft text-critical-text">
            <CircleX className="size-5" aria-hidden />
          </span>
          <div className="min-w-0 flex-1">
            <p className="font-mono text-[13px] text-fg-muted">
              {review.owner}/{review.repo}#{review.pr_number}
            </p>
            <h1 className="mt-1 font-sans text-xl font-semibold text-fg">{review.pr_title ?? 'This review failed'}</h1>
            <p className="mt-3 whitespace-pre-wrap rounded-lg border border-line bg-sunken p-3 font-mono text-[13px] leading-relaxed text-fg-2">
              {review.error}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap justify-end gap-2 border-t border-line bg-raised/60 px-6 py-3.5">
          <Link to="/reviews" className={buttonClasses('ghost')}>
            All reviews
          </Link>
          <Button variant="primary" onClick={() => retry.mutate()} disabled={retry.isPending || review.is_sample}>
            <RotateCcw className="size-4" aria-hidden /> Try again
          </Button>
        </div>
      </Card>
    </div>
  )
}

function DashboardSkeleton() {
  return (
    <div className="mx-auto max-w-[1600px] space-y-5 px-4 py-6 sm:px-6" aria-busy="true">
      <Card className="flex items-center gap-6 p-6">
        <div className="flex-1 space-y-3">
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="h-4 w-1/2" />
        </div>
        <Skeleton className="size-32 rounded-full" />
      </Card>
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_420px]">
        <div className="space-y-4">
          <Skeleton className="h-72" />
          <Skeleton className="h-48" />
        </div>
        <Skeleton className="h-[32rem]" />
      </div>
    </div>
  )
}
