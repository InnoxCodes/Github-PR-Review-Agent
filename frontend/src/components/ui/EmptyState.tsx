import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description: ReactNode
  action?: ReactNode
  className?: string
}

export function EmptyState({ icon: Icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center px-6 py-14 text-center', className)}>
      <div className="relative mb-5">
        <div aria-hidden className="absolute inset-0 rounded-2xl bg-accent/25 blur-xl" />
        <div className="relative grid size-14 place-items-center rounded-2xl border border-line-strong bg-raised text-accent-text">
          <Icon className="size-6" aria-hidden />
        </div>
      </div>
      <h3 className="font-mono text-[15px] font-semibold text-fg">{title}</h3>
      <p className="mt-1.5 max-w-sm text-sm leading-relaxed text-fg-muted">{description}</p>
      {action && <div className="mt-5 flex flex-wrap items-center justify-center gap-2">{action}</div>}
    </div>
  )
}
