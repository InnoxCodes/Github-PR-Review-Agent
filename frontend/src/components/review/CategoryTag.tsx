import { cn } from '@/lib/cn'
import { CATEGORY_META } from '@/lib/meta'
import type { Category } from '@/lib/types'

export function CategoryTag({ category, className }: { category: Category; className?: string }) {
  const meta = CATEGORY_META[category]
  return (
    <span
      title={meta.hint}
      className={cn(
        'inline-flex h-6 items-center gap-1.5 whitespace-nowrap rounded-md border border-line px-2 text-xs font-medium text-fg-2',
        className,
      )}
    >
      <span aria-hidden className="size-2 rounded-[3px]" style={{ background: meta.color }} />
      {meta.label}
    </span>
  )
}
