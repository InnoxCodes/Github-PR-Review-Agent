import { Fragment } from 'react'
import { cn } from '@/lib/cn'

/** Renders `backtick` spans from model-written text as inline code — as text nodes, never HTML. */
export function RichText({ text, className }: { text: string; className?: string }) {
  const parts = text.split(/(`[^`\n]+`)/g)
  return (
    <span className={className}>
      {parts.map((part, index) =>
        part.length > 2 && part.startsWith('`') && part.endsWith('`') ? (
          <code
            key={index}
            className={cn('rounded-[5px] border border-line bg-sunken px-1 py-px font-mono text-[0.86em] text-fg')}
          >
            {part.slice(1, -1)}
          </code>
        ) : (
          <Fragment key={index}>{part}</Fragment>
        ),
      )}
    </span>
  )
}
