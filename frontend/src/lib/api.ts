import type {
  Analytics,
  Health,
  IssueStatus,
  IssueUpdateResult,
  Repository,
  ReviewDetail,
  ReviewStatus,
  ReviewSummary,
} from './types'

const API_BASE = `${import.meta.env.VITE_API_URL ?? ''}/api`

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new ApiError(0, 'Cannot reach the ReviewMind API. Is the backend running on port 8000?')
  }

  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response))
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json()
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail)) return body.detail.map((item: { msg: string }) => item.msg).join('; ')
  } catch {
    // Non-JSON error bodies fall through to the status text.
  }
  return response.statusText || `Request failed (${response.status})`
}

function query(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

export const api = {
  health: () => request<Health>('/health'),

  listReviews: (params: { repository?: string; status?: ReviewStatus; limit?: number } = {}) =>
    request<ReviewSummary[]>(`/reviews${query(params)}`),
  getReview: (id: string) => request<ReviewDetail>(`/reviews/${encodeURIComponent(id)}`),
  createReview: (prUrl: string) =>
    request<ReviewSummary>('/reviews', { method: 'POST', body: JSON.stringify({ pr_url: prUrl }) }),
  deleteReview: (id: string) => request<void>(`/reviews/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  updateIssue: (reviewId: string, issueId: string, status: IssueStatus) =>
    request<IssueUpdateResult>(`/reviews/${encodeURIComponent(reviewId)}/issues/${encodeURIComponent(issueId)}`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),

  listRepos: () => request<Repository[]>('/repos'),
  trackRepo: (repository: string, githubToken?: string) =>
    request<Repository>('/repos', {
      method: 'POST',
      body: JSON.stringify({ repository, github_token: githubToken || null }),
    }),
  deleteRepo: (id: number) => request<void>(`/repos/${id}`, { method: 'DELETE' }),

  analytics: (days: number) => request<Analytics>(`/analytics/summary${query({ days })}`),

  loadSampleData: () => request<{ reviews: number; repositories: number }>('/demo/sample-data', { method: 'POST' }),
  clearSampleData: () => request<void>('/demo/sample-data', { method: 'DELETE' }),
}

export function reviewStreamUrl(reviewId: string, replay = false): string {
  return `${API_BASE}/reviews/${encodeURIComponent(reviewId)}/stream${replay ? '?replay=true' : ''}`
}

export const queryKeys = {
  health: ['health'] as const,
  reviews: (params: object = {}) => ['reviews', params] as const,
  allReviews: ['reviews'] as const,
  review: (id: string) => ['review', id] as const,
  repos: ['repos'] as const,
  analytics: (days: number) => ['analytics', days] as const,
  allAnalytics: ['analytics'] as const,
}

// Mirrors the backend's accepted PR reference formats so the input can validate before submitting.
const PR_REFERENCE =
  /^(?:(?:https?:\/\/)?(?:www\.)?github\.com\/[A-Za-z0-9][A-Za-z0-9-]{0,38}\/[A-Za-z0-9._-]+\/pull\/[1-9]\d*(?:[/?#].*)?|[A-Za-z0-9][A-Za-z0-9-]{0,38}\/[A-Za-z0-9._-]+(?:#|\/pull\/)[1-9]\d*)$/i

export function isPullRequestReference(value: string): boolean {
  return PR_REFERENCE.test(value.trim())
}
