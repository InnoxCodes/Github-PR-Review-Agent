import { cn } from '@/lib/cn'
import { SEVERITY_META } from '@/lib/meta'
import type { Severity } from '@/lib/types'

interface SeverityBadgeProps {
  severity: Severity
  pulse?: boolean
  className?: string
}

export function SeverityBadge({ severity, pulse = false, className }: SeverityBadgeProps) {
  const meta = SEVERITY_META[severity]
  const Icon = meta.icon
  return (
    <span
      className={cn(
        'inline-flex h-6 items-center gap-1.5 rounded-md pl-1.5 pr-2 text-xs font-semibold',
        meta.soft,
        meta.text,
        className,
      )}
    >
      <span className={cn('relative grid place-items-center rounded-full', pulse && 'pulse-critical')}>
        <Icon className="size-3.5" aria-hidden />
      </span>
      {meta.label}
    </span>
  )
}
