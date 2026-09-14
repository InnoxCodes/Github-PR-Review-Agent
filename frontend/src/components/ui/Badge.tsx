import type { ComponentProps } from 'react'
import { cn } from '@/lib/cn'

const tones = {
  neutral: 'bg-muted text-fg-2',
  outline: 'border border-line-strong text-fg-muted',
  accent: 'bg-accent-soft text-accent-text',
  critical: 'bg-critical-soft text-critical-text',
  warning: 'bg-warning-soft text-warning-text',
  info: 'bg-info-soft text-info-text',
  good: 'bg-good-soft text-good-text',
} as const

export interface BadgeProps extends ComponentProps<'span'> {
  tone?: keyof typeof tones
}

export function Badge({ tone = 'neutral', className, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex h-6 items-center gap-1.5 whitespace-nowrap rounded-md px-2 text-xs font-medium [&_svg]:size-3.5 [&_svg]:shrink-0',
        tones[tone],
        className,
      )}
      {...props}
    />
  )
}
