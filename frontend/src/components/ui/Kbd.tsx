import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

export function Kbd({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <kbd
      className={cn(
        'inline-flex h-5 min-w-5 items-center justify-center rounded-[5px] border border-line-strong bg-raised px-1',
        'font-mono text-xs leading-none text-fg-muted shadow-[inset_0_-1px_0_var(--rm-line-strong)]',
        className,
      )}
    >
      {children}
    </kbd>
  )
}
