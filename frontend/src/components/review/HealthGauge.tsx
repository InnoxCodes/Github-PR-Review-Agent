import { motion, useReducedMotion } from 'framer-motion'
import { AnimatedNumber } from '@/components/ui/AnimatedNumber'
import { cn } from '@/lib/cn'
import { GRADE_META, gradeFor } from '@/lib/meta'

interface HealthGaugeProps {
  score: number | null
  size?: number
  compact?: boolean
  className?: string
}

const ARC = 0.75 // a 270° gauge, open at the bottom

/**
 * Radial meter for the PR health score. The fill carries the grade (good → warning →
 * critical); the track is the same hue at low opacity, so the state reads across the whole ring.
 */
export function HealthGauge({ score, size = 140, compact = false, className }: HealthGaugeProps) {
  const reduceMotion = useReducedMotion()
  const grade = gradeFor(score)
  const color = grade ? GRADE_META[grade].color : 'var(--rm-fg-subtle)'
  const stroke = compact ? Math.max(3, size * 0.09) : size * 0.075
  const radius = (size - stroke) / 2 - 1
  const circumference = 2 * Math.PI * radius
  const arcLength = circumference * ARC
  const value = Math.max(0, Math.min(100, score ?? 0))
  const label = grade ? `Health score ${score} out of 100, ${GRADE_META[grade].label}` : 'No health score yet'

  return (
    <div role="img" aria-label={label} className={cn('relative shrink-0', className)} style={{ width: size, height: size }}>
      <svg viewBox={`0 0 ${size} ${size}`} className="rotate-[135deg]" width={size} height={size} aria-hidden>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeOpacity={0.16}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${arcLength} ${circumference}`}
          style={{ transition: 'stroke 500ms ease' }}
        />
        {score !== null && (
          <motion.circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${arcLength} ${circumference}`}
            initial={{ strokeDashoffset: reduceMotion ? arcLength * (1 - value / 100) : arcLength }}
            animate={{ strokeDashoffset: arcLength * (1 - value / 100) }}
            transition={{ duration: reduceMotion ? 0 : 1.1, ease: [0.22, 1, 0.36, 1] }}
            style={{
              transition: 'stroke 500ms ease',
              filter: compact ? undefined : `drop-shadow(0 0 6px color-mix(in oklab, ${color} 55%, transparent))`,
            }}
          />
        )}
      </svg>
      <div aria-hidden className="absolute inset-0 grid place-items-center">
        <div className="text-center leading-none">
          <span
            className="font-sans font-semibold tracking-tight text-fg"
            style={{ fontSize: compact ? size * 0.32 : size * 0.27 }}
          >
            {score === null ? (
              <span className="text-fg-subtle">-</span>
            ) : (
              <AnimatedNumber value={value} format={(v) => String(Math.round(v))} />
            )}
          </span>
          {!compact && <div className="mt-1.5 text-xs font-medium tracking-[0.12em] text-fg-muted">/ 100</div>}
        </div>
      </div>
    </div>
  )
}
