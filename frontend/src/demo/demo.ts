// Backend-free implementation of the API for the hosted demo (VITE_DEMO=1).
// It serves the exported sample reviews, recomputes scores and analytics in the browser the
// way the backend does, and keeps triage decisions in localStorage.
import { ApiError } from '@/lib/api'
import { CATEGORIES, gradeFor } from '@/lib/meta'
import type {
  Analytics,
  Category,
  Health,
  Issue,
  IssueStatus,
  IssueUpdateResult,
  Repository,
  ReviewDetail,
  ReviewStatus,
  ReviewSummary,
  SeverityCounts,
  StreamEvent,
} from '@/lib/types'
import raw from './snapshot.json'

interface Snapshot {
  exported_at: string
  reviews: ReviewDetail[]
  events: Record<string, { id: number; type: StreamEvent['type']; data: unknown }[]>
  repos: Repository[]
}

const STORAGE_KEY = 'reviewmind:demo-triage'
const MINUTES_PER_FILE = 6
const snapshot = raw as unknown as Snapshot
const LIVE: IssueStatus[] = ['open', 'accepted']

const SEVERITY_POINTS = { critical: 18, warning: 6, info: 1.5 } as const
const CATEGORY_WEIGHT: Record<Category, number> = {
  security: 1.5,
  bug: 1.25,
  performance: 1,
  'missing-test': 0.8,
  complexity: 0.8,
  style: 0.5,
}
const CONFIDENCE_WEIGHT = { high: 1, medium: 0.8, low: 0.5 } as const

function readSaved(): Record<string, IssueStatus> {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}')
  } catch {
    return {}
  }
}

function persist(reviews: ReviewDetail[]) {
  const saved: Record<string, IssueStatus> = {}
  for (const review of reviews) for (const issue of review.issues) saved[issue.id] = issue.status
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(saved))
  } catch {
    // Storage blocked: triage still works for this visit.
  }
}

// Timestamps are shifted so the newest sample review always looks recent, however old the snapshot is.
const shift = Date.now() - Date.parse(snapshot.exported_at)
const moved = (iso: string | null) => (iso ? new Date(Date.parse(iso) + shift).toISOString() : null)

const saved = readSaved()
const reviews: ReviewDetail[] = structuredClone(snapshot.reviews).map((review) => ({
  ...review,
  created_at: moved(review.created_at)!,
  completed_at: moved(review.completed_at),
  issues: review.issues.map((issue) => ({
    ...issue,
    status: saved[issue.id] ?? issue.status,
    created_at: moved(issue.created_at)!,
    resolved_at: moved(issue.resolved_at),
  })),
}))

function changedLines(review: ReviewDetail): number {
  return review.files.filter((file) => file.state !== 'skipped').reduce((sum, file) => sum + file.additions + file.deletions, 0)
}

function score(review: ReviewDetail): number {
  const size = Math.max(1, Math.sqrt(changedLines(review) / 100))
  let absolute = 0
  let density = 0
  for (const issue of review.issues.filter((item) => LIVE.includes(item.status))) {
    const points = SEVERITY_POINTS[issue.severity] * CATEGORY_WEIGHT[issue.category] * CONFIDENCE_WEIGHT[issue.confidence]
    if (issue.severity === 'critical') absolute += points
    else density += points
  }
  return Math.round(Math.min(100, Math.max(0, 100 - absolute - density / size)))
}

function counts(review: ReviewDetail): SeverityCounts {
  const result: SeverityCounts = { critical: 0, warning: 0, info: 0 }
  for (const issue of review.issues) if (LIVE.includes(issue.status)) result[issue.severity] += 1
  return result
}

function refresh(review: ReviewDetail): ReviewDetail {
  const health = score(review)
  review.health_score = health
  review.grade = gradeFor(health)
  review.issue_counts = counts(review)
  review.issues_total = review.issues.length
  review.open_issues = review.issues.filter((issue) => issue.status === 'open').length
  return review
}
reviews.forEach(refresh)

function summary(review: ReviewDetail): ReviewSummary {
  const {
    pr_body: _body, pr_state: _state, pr_draft: _draft, pr_merged: _merged, head_sha: _sha, changed_files: _files,
    commits: _commits, summary: _summary, provider: _provider, initial_health_score: _initial, tokens: _tokens,
    llm_calls: _calls, invalid_outputs: _invalid, files: _f, issues: _i, ...rest
  } = review
  return rest
}

const find = (id: string) => {
  const review = reviews.find((item) => item.id === id)
  if (!review) throw new ApiError(404, 'Review not found.')
  return review
}

const unavailable = (what: string) =>
  new ApiError(503, `${what} needs the ReviewMind backend. This hosted demo runs on bundled sample reviews; clone the repo to run it live.`)

function repositories(): Repository[] {
  return snapshot.repos
    .map((repo) => {
      const done = reviews
        .filter((review) => review.status === 'completed' && review.owner.toLowerCase() + '/' + review.repo.toLowerCase() === repo.full_name.toLowerCase())
        .sort((a, b) => a.created_at.localeCompare(b.created_at))
      const scores = done.map((review) => review.health_score).filter((value): value is number => value !== null)
      return {
        ...repo,
        created_at: moved(repo.created_at)!,
        review_count: done.length,
        last_reviewed_at: done.at(-1)?.created_at ?? null,
        average_health_score: scores.length ? Math.round((scores.reduce((a, b) => a + b, 0) / scores.length) * 10) / 10 : null,
        open_issues: done.reduce((sum, review) => sum + review.open_issues, 0),
        score_history: scores.slice(-12),
        issue_history: done.map((review) => review.issues_total).slice(-12),
      }
    })
    .sort((a, b) => (b.last_reviewed_at ?? '').localeCompare(a.last_reviewed_at ?? ''))
}

function weekStart(iso: string): string {
  const date = new Date(iso)
  const day = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()))
  day.setUTCDate(day.getUTCDate() - ((day.getUTCDay() + 6) % 7))
  return day.toISOString().slice(0, 10)
}

function analytics(days: number): Analytics {
  const since = Date.now() - days * 86_400_000
  const done = reviews
    .filter((review) => review.status === 'completed' && Date.parse(review.created_at) >= since)
    .sort((a, b) => a.created_at.localeCompare(b.created_at))
  const issues = done.flatMap((review) => review.issues)
  const by = (status: IssueStatus) => issues.filter((issue) => issue.status === status).length
  const triaged = by('accepted') + by('dismissed') + by('false_positive')
  const scores = done.map((review) => review.health_score).filter((value): value is number => value !== null)
  const filesReviewed = done.reduce((sum, review) => sum + review.files.filter((file) => file.state === 'done').length, 0)
  const costs = done.map((review) => review.cost_usd).filter((value): value is number => value !== null)
  const durations = done.map((review) => review.duration_ms).filter((value): value is number => !!value)

  const weeks: string[] = []
  if (done.length) {
    const cursor = new Date(`${weekStart(done[0].created_at)}T00:00:00Z`)
    const end = weekStart(new Date().toISOString())
    while (cursor.toISOString().slice(0, 10) <= end) {
      weeks.push(cursor.toISOString().slice(0, 10))
      cursor.setUTCDate(cursor.getUTCDate() + 7)
    }
  }
  const weekly = weeks.slice(-26).map((week) => {
    const inWeek = done.filter((review) => weekStart(review.created_at) === week)
    const tally = Object.fromEntries(CATEGORIES.map((category) => [category, 0])) as Record<Category, number>
    for (const issue of inWeek.flatMap((review) => review.issues)) tally[issue.category] += 1
    return { week_start: week, reviews: inWeek.length, counts: tally }
  })

  return {
    days,
    totals: {
      prs_reviewed: done.length,
      files_reviewed: filesReviewed,
      issues_found: issues.length,
      open_issues: by('open'),
      accepted: by('accepted'),
      dismissed: by('dismissed'),
      false_positives: by('false_positive'),
    },
    severity_counts: {
      critical: issues.filter((issue) => issue.severity === 'critical').length,
      warning: issues.filter((issue) => issue.severity === 'warning').length,
      info: issues.filter((issue) => issue.severity === 'info').length,
    },
    false_positive_rate: triaged ? Math.round((by('false_positive') / triaged) * 10_000) / 10_000 : null,
    acceptance_rate: triaged ? Math.round((by('accepted') / triaged) * 10_000) / 10_000 : null,
    average_health_score: scores.length ? Math.round((scores.reduce((a, b) => a + b, 0) / scores.length) * 10) / 10 : null,
    minutes_saved: Math.round(filesReviewed * MINUTES_PER_FILE * 10) / 10,
    minutes_per_file: MINUTES_PER_FILE,
    total_cost_usd: costs.length ? Math.round(costs.reduce((a, b) => a + b, 0) * 10_000) / 10_000 : null,
    total_tokens: done.reduce(
      (sum, review) => sum + review.tokens.input_tokens + review.tokens.output_tokens + review.tokens.cache_read_tokens + review.tokens.cache_creation_tokens,
      0,
    ),
    average_review_seconds: durations.length ? Math.round((durations.reduce((a, b) => a + b, 0) / durations.length / 100)) / 10 : null,
    score_trend: done
      .filter((review) => review.health_score !== null)
      .map((review) => ({
        review_id: review.id,
        label: `${review.repo}#${review.pr_number}`,
        title: review.pr_title,
        date: review.created_at,
        score: review.health_score!,
      })),
    categories: CATEGORIES.map((category) => {
      const subset = issues.filter((issue) => issue.category === category)
      const severity = (value: Issue['severity']) => subset.filter((issue) => issue.severity === value).length
      const status = (value: IssueStatus) => subset.filter((issue) => issue.status === value).length
      return {
        category,
        total: subset.length,
        critical: severity('critical'),
        warning: severity('warning'),
        info: severity('info'),
        open: status('open'),
        accepted: status('accepted'),
        dismissed: status('dismissed'),
        false_positive: status('false_positive'),
      }
    }),
    weekly,
  }
}

export const demoApi = {
  health: async (): Promise<Health> => ({
    status: 'ok',
    version: 'demo',
    llm: { configured: false, provider: null, model: null, message: 'Hosted demo on bundled sample reviews.' },
    github_token_configured: false,
    sample_data_loaded: true,
    demo: true,
  }),
  listReviews: async (params: { repository?: string; status?: ReviewStatus; limit?: number } = {}) =>
    reviews
      .filter((review) => !params.repository || `${review.owner}/${review.repo}`.toLowerCase() === params.repository.toLowerCase())
      .filter((review) => !params.status || review.status === params.status)
      .sort((a, b) => b.created_at.localeCompare(a.created_at))
      .slice(0, params.limit ?? 50)
      .map(summary),
  getReview: async (id: string) => structuredClone(find(id)),
  createReview: async (): Promise<ReviewSummary> => {
    throw unavailable('Reviewing a new pull request')
  },
  deleteReview: async (): Promise<void> => {
    throw unavailable('Deleting reviews')
  },
  updateIssue: async (reviewId: string, issueId: string, status: IssueStatus): Promise<IssueUpdateResult> => {
    const review = find(reviewId)
    const issue = review.issues.find((item) => item.id === issueId)
    if (!issue) throw new ApiError(404, 'Issue not found.')
    issue.status = status
    issue.resolved_at = status === 'open' ? null : new Date().toISOString()
    refresh(review)
    persist(reviews)
    return {
      issue: { ...issue },
      health_score: review.health_score,
      grade: review.grade,
      issue_counts: { ...review.issue_counts },
      open_issues: review.open_issues,
    }
  },
  listRepos: async () => repositories(),
  trackRepo: async (): Promise<Repository> => {
    throw unavailable('Tracking a repository')
  },
  deleteRepo: async (): Promise<void> => {
    throw unavailable('Removing a repository')
  },
  analytics: async (days: number) => analytics(days),
  loadSampleData: async () => ({ reviews: reviews.length, repositories: snapshot.repos.length }),
  clearSampleData: async (): Promise<void> => undefined,
}

export function demoEvents(reviewId: string) {
  return snapshot.events[reviewId] ?? []
}
