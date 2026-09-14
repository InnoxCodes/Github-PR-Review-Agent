import { cn } from '@/lib/cn'
import { CONFIDENCE_LEVEL } from '@/lib/meta'
import type { Confidence } from '@/lib/types'

export function ConfidenceMeter({ confidence, className }: { confidence: Confidence; className?: string }) {
  const level = CONFIDENCE_LEVEL[confidence]
  const label = `${confidence[0].toUpperCase()}${confidence.slice(1)} confidence`
  return (
    <span className={cn('inline-flex items-center gap-1.5 text-xs text-fg-muted', className)} title={label}>
      <span aria-hidden className="flex items-end gap-[2px]">
        {[1, 2, 3].map((bar) => (
          <span
            key={bar}
            className={cn('w-[3px] rounded-full', bar <= level ? 'bg-fg-muted' : 'bg-line-strong')}
            style={{ height: 4 + bar * 3 }}
          />
        ))}
      </span>
      <span className="sr-only sm:not-sr-only">{confidence}</span>
    </span>
  )
}
