import { motion } from 'framer-motion'
import { useChartTheme } from '@/lib/chartTheme'

interface SparklineProps {
  values: number[]
  label: string
  width?: number
  height?: number
  domain?: [number, number]
}

/** De-emphasised history with the latest point in the accent hue. */
export function Sparkline({ values, label, width = 132, height = 36, domain }: SparklineProps) {
  const theme = useChartTheme()
  if (values.length < 2) {
    return <span className="text-xs text-fg-subtle">Needs 2+ reviews</span>
  }

  const [min, max] = domain ?? [Math.min(...values), Math.max(...values)]
  const span = max - min || 1
  const pad = 5
  const points = values.map((value, index) => [
    pad + (index / (values.length - 1)) * (width - pad * 2),
    pad + (1 - (value - min) / span) * (height - pad * 2),
  ])
  const path = points.map(([x, y], index) => `${index ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const [lastX, lastY] = points[points.length - 1]

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label}>
      <motion.path
        d={path}
        fill="none"
        stroke={theme.fgSubtle}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 0.8, ease: 'easeOut' }}
      />
      <motion.circle
        cx={lastX}
        cy={lastY}
        r={3.5}
        fill={theme.series[0]}
        stroke={theme.surface}
        strokeWidth={2}
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ delay: 0.7, type: 'spring', stiffness: 500, damping: 20 }}
      />
    </svg>
  )
}
