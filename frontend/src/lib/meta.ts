import {
  Ban,
  Bug,
  CircleCheck,
  CircleDot,
  Flag,
  FlaskConical,
  Info,
  Layers,
  OctagonAlert,
  Paintbrush,
  ShieldAlert,
  TriangleAlert,
  Zap,
  type LucideIcon,
} from 'lucide-react'
import type { Category, Confidence, Grade, IssueStatus, ReviewStatus, Severity } from './types'

export const ACTIVE_STATUSES: ReviewStatus[] = ['queued', 'fetching', 'reviewing']

export function isActive(status: ReviewStatus): boolean {
  return ACTIVE_STATUSES.includes(status)
}

export const CATEGORIES: Category[] = ['bug', 'security', 'performance', 'missing-test', 'complexity', 'style']
export const SEVERITIES: Severity[] = ['critical', 'warning', 'info']

// Categorical identity: fixed slot order, validated with the dataviz palette checks.
export const CATEGORY_META: Record<Category, { label: string; icon: LucideIcon; color: string; hint: string }> = {
  bug: { label: 'Bug', icon: Bug, color: 'var(--rm-series-1)', hint: 'Incorrect behaviour' },
  security: { label: 'Security', icon: ShieldAlert, color: 'var(--rm-series-2)', hint: 'Vulnerabilities and unsafe data handling' },
  performance: { label: 'Performance', icon: Zap, color: 'var(--rm-series-3)', hint: 'Avoidable work on hot paths' },
  'missing-test': { label: 'Missing test', icon: FlaskConical, color: 'var(--rm-series-4)', hint: 'New behaviour without tests' },
  complexity: { label: 'Complexity', icon: Layers, color: 'var(--rm-series-5)', hint: 'Hard to understand or change' },
  style: { label: 'Style', icon: Paintbrush, color: 'var(--rm-series-6)', hint: 'Readability and conventions' },
}

// Severity is status, not identity: reserved colours, always paired with an icon and a label.
export const SEVERITY_META: Record<
  Severity,
  { label: string; icon: LucideIcon; text: string; soft: string; dot: string; border: string; rank: number }
> = {
  critical: {
    label: 'Critical',
    icon: OctagonAlert,
    text: 'text-critical-text',
    soft: 'bg-critical-soft',
    dot: 'bg-critical',
    border: 'border-l-critical',
    rank: 0,
  },
  warning: {
    label: 'Warning',
    icon: TriangleAlert,
    text: 'text-warning-text',
    soft: 'bg-warning-soft',
    dot: 'bg-warning',
    border: 'border-l-warning',
    rank: 1,
  },
  info: {
    label: 'Info',
    icon: Info,
    text: 'text-info-text',
    soft: 'bg-info-soft',
    dot: 'bg-info',
    border: 'border-l-info',
    rank: 2,
  },
}

export const GRADE_META: Record<Grade, { label: string; icon: LucideIcon; color: string; text: string; soft: string }> = {
  healthy: { label: 'Healthy', icon: CircleCheck, color: 'var(--rm-good)', text: 'text-good-text', soft: 'bg-good-soft' },
  needs_attention: {
    label: 'Needs attention',
    icon: TriangleAlert,
    color: 'var(--rm-warning)',
    text: 'text-warning-text',
    soft: 'bg-warning-soft',
  },
  at_risk: { label: 'At risk', icon: OctagonAlert, color: 'var(--rm-critical)', text: 'text-critical-text', soft: 'bg-critical-soft' },
}

export const ISSUE_STATUS_META: Record<IssueStatus, { label: string; icon: LucideIcon; text: string }> = {
  open: { label: 'Open', icon: CircleDot, text: 'text-fg-muted' },
  accepted: { label: 'Accepted', icon: CircleCheck, text: 'text-good-text' },
  dismissed: { label: 'Dismissed', icon: Ban, text: 'text-fg-muted' },
  false_positive: { label: 'False positive', icon: Flag, text: 'text-warning-text' },
}

export const CONFIDENCE_LEVEL: Record<Confidence, number> = { high: 3, medium: 2, low: 1 }

export const SKIP_REASON_LABEL: Record<string, string> = {
  lockfile: 'Lockfile',
  generated: 'Generated code',
  vendored: 'Vendored dependency',
  asset: 'Binary or asset',
  docs: 'Documentation',
  deleted: 'Deleted file',
  no_changes: 'No content changes',
  no_patch: 'Diff unavailable',
  too_large: 'Too large to review',
  unparseable: "Couldn't parse diff",
  file_limit: 'Over the file limit',
}

export function gradeFor(score: number | null | undefined): Grade | null {
  if (score === null || score === undefined) return null
  if (score >= 80) return 'healthy'
  if (score >= 50) return 'needs_attention'
  return 'at_risk'
}
