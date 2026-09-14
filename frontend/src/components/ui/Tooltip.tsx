import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

interface TooltipProps {
  content: ReactNode
  children: ReactNode
  side?: 'top' | 'bottom'
  className?: string
}

/** Hover and keyboard-focus tooltip for short, supplementary labels. Never the only way to learn something. */
export function Tooltip({ content, children, side = 'top', className }: TooltipProps) {
  return (
    <span className={cn('group/tooltip relative inline-flex', className)}>
      {children}
      <span
        role="tooltip"
        className={cn(
          'pointer-events-none absolute left-1/2 z-40 -translate-x-1/2 whitespace-nowrap rounded-md border border-line-strong bg-raised px-2 py-1',
          'text-xs text-fg-2 opacity-0 shadow-pop transition-opacity duration-150',
          'group-hover/tooltip:opacity-100 group-focus-within/tooltip:opacity-100',
          side === 'top' ? 'bottom-full mb-2' : 'top-full mt-2',
        )}
      >
        {content}
      </span>
    </span>
  )
}
