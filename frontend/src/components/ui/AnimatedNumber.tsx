import { animate, useReducedMotion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { formatNumber } from '@/lib/format'

interface AnimatedNumberProps {
  value: number
  format?: (value: number) => string
  duration?: number
  className?: string
}

export function AnimatedNumber({ value, format = (v) => formatNumber(Math.round(v)), duration = 0.9, className }: AnimatedNumberProps) {
  const reduceMotion = useReducedMotion()
  const [display, setDisplay] = useState(reduceMotion ? value : 0)
  const current = useRef(display)

  useEffect(() => {
    if (reduceMotion) {
      current.current = value
      return
    }
    const controls = animate(current.current, value, {
      duration,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (latest) => {
        current.current = latest
        setDisplay(latest)
      },
    })
    return () => controls.stop()
  }, [value, duration, reduceMotion])

  return <span className={className}>{format(reduceMotion ? value : display)}</span>
}
