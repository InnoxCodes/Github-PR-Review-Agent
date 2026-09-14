import { SEVERITY_META } from '@/lib/meta'
import type { Category, Issue, IssueStatus, Severity } from '@/lib/types'

export type StatusFilter = 'open' | 'resolved' | 'all'
export type SortMode = 'severity' | 'location'

export interface IssueFilters {
  status: StatusFilter
  severities: Severity[]
  category: Category | 'all'
  sort: SortMode
}

export const DEFAULT_FILTERS: IssueFilters = { status: 'open', severities: [], category: 'all', sort: 'severity' }

export function matchesStatus(status: IssueStatus, filter: StatusFilter): boolean {
  if (filter === 'all') return true
  return filter === 'open' ? status === 'open' : status !== 'open'
}

export function applyIssueFilters(
  issues: Issue[],
  filters: IssueFilters,
  filePosition: Map<number, number>,
  keep: ReadonlySet<string> = new Set(),
): Issue[] {
  const byLocation = (a: Issue, b: Issue) =>
    (filePosition.get(a.file_id) ?? 0) - (filePosition.get(b.file_id) ?? 0) || a.line_number - b.line_number

  return issues
    .filter((issue) => keep.has(issue.id) || matchesStatus(issue.status, filters.status))
    .filter((issue) => filters.severities.length === 0 || filters.severities.includes(issue.severity))
    .filter((issue) => filters.category === 'all' || issue.category === filters.category)
    .sort((a, b) =>
      filters.sort === 'severity'
        ? SEVERITY_META[a.severity].rank - SEVERITY_META[b.severity].rank || byLocation(a, b)
        : byLocation(a, b),
    )
}
