// Mirrors backend/app/schemas.py, the API contract the dashboard is written against.

export type Severity = 'critical' | 'warning' | 'info'
export type Category = 'bug' | 'security' | 'performance' | 'missing-test' | 'complexity' | 'style'
export type Confidence = 'high' | 'medium' | 'low'
export type IssueStatus = 'open' | 'accepted' | 'dismissed' | 'false_positive'
export type ReviewStatus = 'queued' | 'fetching' | 'reviewing' | 'completed' | 'failed'
export type FileState = 'pending' | 'reviewing' | 'done' | 'failed' | 'skipped'
export type Grade = 'healthy' | 'needs_attention' | 'at_risk'

export interface SeverityCounts {
  critical: number
  warning: number
  info: number
}

export interface Issue {
  id: string
  review_id: string
  file_id: number
  filename: string
  line_number: number
  end_line: number | null
  severity: Severity
  category: Category
  confidence: Confidence
  title: string
  comment: string
  suggested_fix: string | null
  status: IssueStatus
  created_at: string
  resolved_at: string | null
}

export interface DiffLine {
  type: 'add' | 'delete' | 'context'
  content: string
  old_line: number | null
  new_line: number | null
}

export interface Hunk {
  old_start: number
  old_lines: number
  new_start: number
  new_lines: number
  section: string
  lines: DiffLine[]
}

export interface ReviewFile {
  id: number
  filename: string
  previous_filename: string | null
  git_status: string
  language: string
  additions: number
  deletions: number
  skip_reason: string | null
  state: FileState
  chunk_count: number
  summary: string | null
  error: string | null
  issue_count: number
  cost_usd: number | null
}

export interface ReviewFileDetail extends ReviewFile {
  hunks: Hunk[]
}

export interface ReviewSummary {
  id: string
  status: ReviewStatus
  status_message: string | null
  pr_url: string
  owner: string
  repo: string
  pr_number: number
  pr_title: string | null
  pr_author: string | null
  pr_author_avatar: string | null
  base_ref: string | null
  head_ref: string | null
  health_score: number | null
  grade: Grade | null
  issue_counts: SeverityCounts
  issues_total: number
  open_issues: number
  files_total: number
  files_done: number
  additions: number
  deletions: number
  model: string | null
  cost_usd: number | null
  is_sample: boolean
  error: string | null
  created_at: string
  completed_at: string | null
  duration_ms: number | null
}

export interface ReviewDetail extends ReviewSummary {
  pr_body: string | null
  pr_state: string | null
  pr_draft: boolean
  pr_merged: boolean
  head_sha: string | null
  changed_files: number
  commits: number
  summary: string | null
  provider: string | null
  initial_health_score: number | null
  tokens: {
    input_tokens: number
    output_tokens: number
    cache_creation_tokens: number
    cache_read_tokens: number
  }
  llm_calls: number
  invalid_outputs: number
  files: ReviewFileDetail[]
  issues: Issue[]
}

export interface IssueUpdateResult {
  issue: Issue
  health_score: number | null
  grade: Grade | null
  issue_counts: SeverityCounts
  open_issues: number
}

export interface Repository {
  id: number
  owner: string
  name: string
  full_name: string
  html_url: string
  description: string | null
  language: string | null
  stars: number
  is_private: boolean
  default_branch: string | null
  has_token: boolean
  token_hint: string | null
  created_at: string
  review_count: number
  last_reviewed_at: string | null
  average_health_score: number | null
  open_issues: number
  score_history: number[]
  issue_history: number[]
}

export interface Health {
  status: 'ok'
  version: string
  llm: { configured: boolean; provider: string | null; model: string | null; message: string }
  github_token_configured: boolean
  sample_data_loaded: boolean
  demo?: boolean
}

export interface CategoryBreakdown {
  category: Category
  total: number
  critical: number
  warning: number
  info: number
  open: number
  accepted: number
  dismissed: number
  false_positive: number
}

export interface Analytics {
  days: number
  totals: {
    prs_reviewed: number
    files_reviewed: number
    issues_found: number
    open_issues: number
    accepted: number
    dismissed: number
    false_positives: number
  }
  severity_counts: SeverityCounts
  false_positive_rate: number | null
  acceptance_rate: number | null
  average_health_score: number | null
  minutes_saved: number
  minutes_per_file: number
  total_cost_usd: number | null
  total_tokens: number
  average_review_seconds: number | null
  score_trend: { review_id: string; label: string; title: string | null; date: string; score: number }[]
  categories: CategoryBreakdown[]
  weekly: { week_start: string; reviews: number; counts: Record<Category, number> }[]
}

// ---- Server-Sent Events -------------------------------------------------------------------

export type StreamEvent =
  | { type: 'status'; data: { status: ReviewStatus; message: string; model?: string } }
  | { type: 'pr'; data: { review: ReviewSummary; files: ReviewFile[] } }
  | { type: 'file.started'; data: { file_id: number; filename: string; chunks: number } }
  | { type: 'issues'; data: { file_id: number; filename: string; chunk: number; issues: Issue[] } }
  | { type: 'file.retry'; data: { file_id: number | null; filename: string; attempt: number; reason: string } }
  | {
      type: 'file.completed'
      data: {
        file_id: number
        filename: string
        state: FileState
        summary: string | null
        error: string | null
        issue_count: number
        files_done: number
        files_total: number
        cost_usd: number | null
        tokens: number
      }
    }
  | { type: 'review.completed'; data: { review: ReviewSummary } }
  | { type: 'review.failed'; data: { error: string; review?: ReviewSummary } }
