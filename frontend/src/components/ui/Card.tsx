import type { ComponentProps, ReactNode } from 'react'
import { cn } from '@/lib/cn'

export function Card({ className, ...props }: ComponentProps<'div'>) {
  return <div className={cn('rounded-2xl border border-line bg-surface shadow-card', className)} {...props} />
}

interface CardHeaderProps {
  title: ReactNode
  description?: ReactNode
  action?: ReactNode
  icon?: ReactNode
  className?: string
}

export function CardHeader({ title, description, action, icon, className }: CardHeaderProps) {
  return (
    <div className={cn('flex items-start justify-between gap-4 px-5 pt-5', className)}>
      <div className="flex min-w-0 items-start gap-3">
        {icon && (
          <div className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg border border-line bg-raised text-fg-muted">
            {icon}
          </div>
        )}
        <div className="min-w-0">
          <h2 className="font-mono text-[15px] font-semibold text-fg">{title}</h2>
          {description && <p className="mt-0.5 text-[13px] text-fg-muted">{description}</p>}
        </div>
      </div>
      {action && <div className="flex shrink-0 items-center gap-2">{action}</div>}
    </div>
  )
}
