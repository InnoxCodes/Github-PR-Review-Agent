import { useMemo } from 'react'
import { useTheme } from './theme'

export interface ChartTheme {
  surface: string
  grid: string
  axis: string
  text: string
  fg: string
  fg2: string
  fgSubtle: string
  muted: string
  series: string[]
  good: string
  warning: string
  critical: string
}

/** Resolves the CSS design tokens to concrete colours for SVG chart libraries, per theme. */
export function useChartTheme(): ChartTheme {
  const { theme } = useTheme()
  return useMemo(() => {
    const styles = getComputedStyle(document.documentElement)
    const read = (name: string) => styles.getPropertyValue(name).trim()
    return {
      surface: read('--rm-surface'),
      grid: read('--rm-chart-grid'),
      axis: read('--rm-chart-axis'),
      text: read('--rm-chart-text'),
      fg: read('--rm-fg'),
      fg2: read('--rm-fg-2'),
      fgSubtle: read('--rm-fg-subtle'),
      muted: read('--rm-muted'),
      series: [1, 2, 3, 4, 5, 6].map((slot) => read(`--rm-series-${slot}`)),
      good: read('--rm-good'),
      warning: read('--rm-warning'),
      critical: read('--rm-critical'),
    }
    // theme is the cache key: the values come from CSS, which changes with it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [theme])
}
