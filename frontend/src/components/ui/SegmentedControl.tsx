import { motion } from 'framer-motion'
import { useId, useRef, type KeyboardEvent, type ReactNode } from 'react'
import { cn } from '@/lib/cn'
import { spring } from '@/lib/motion'

export interface SegmentOption<T extends string> {
  value: T
  label: ReactNode
  icon?: ReactNode
  count?: number
}

interface SegmentedControlProps<T extends string> {
  value: T
  onChange: (value: T) => void
  options: SegmentOption<T>[]
  label: string
  className?: string
}

export function SegmentedControl<T extends string>({ value, onChange, options, label, className }: SegmentedControlProps<T>) {
  const layoutId = useId()
  const refs = useRef<(HTMLButtonElement | null)[]>([])

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const step = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0
    if (!step) return
    event.preventDefault()
    const next = (index + step + options.length) % options.length
    onChange(options[next].value)
    refs.current[next]?.focus()
  }

  return (
    <div role="radiogroup" aria-label={label} className={cn('inline-flex rounded-lg border border-line bg-sunken p-0.5', className)}>
      {options.map((option, index) => {
        const active = option.value === value
        return (
          <button
            key={option.value}
            ref={(element) => {
              refs.current[index] = element
            }}
            type="button"
            role="radio"
            aria-checked={active}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(option.value)}
            onKeyDown={(event) => onKeyDown(event, index)}
            className={cn(
              'relative isolate inline-flex h-7 items-center gap-1.5 whitespace-nowrap rounded-md px-2.5 text-[13px] font-medium transition-colors duration-200',
              active ? 'text-fg' : 'text-fg-muted hover:text-fg',
            )}
          >
            {active && (
              <motion.span
                layoutId={layoutId}
                transition={spring}
                className="absolute inset-0 -z-10 rounded-md bg-raised shadow-card ring-1 ring-line-strong"
              />
            )}
            {option.icon}
            {option.label}
            {option.count !== undefined && <span className="tabular text-xs text-fg-subtle">{option.count}</span>}
          </button>
        )
      })}
    </div>
  )
}
