const compactFormatter = new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 })
const relativeFormatter = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })
const shortDateFormatter = new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric' })
const fullDateFormatter = new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeStyle: 'short' })

export function formatNumber(value: number): string {
  return value.toLocaleString('en')
}

export function formatCompact(value: number): string {
  return Math.abs(value) < 10_000 ? formatNumber(value) : compactFormatter.format(value)
}

export function formatCost(usd: number | null | undefined): string {
  if (usd === null || usd === undefined) return '-'
  if (usd === 0) return '$0.00'
  if (usd < 0.01) return '<$0.01'
  return `$${usd.toFixed(usd < 100 ? 2 : 0)}`
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '-'
  const seconds = ms / 1000
  if (seconds < 60) return `${seconds.toFixed(seconds < 10 ? 1 : 0)}s`
  const minutes = Math.floor(seconds / 60)
  return `${minutes}m ${Math.round(seconds % 60)}s`
}

export function formatMinutes(minutes: number): string {
  if (minutes < 60) return `${Math.round(minutes)} min`
  const hours = minutes / 60
  return `${hours.toFixed(hours < 10 ? 1 : 0)} h`
}

export function formatPercent(ratio: number | null | undefined): string {
  if (ratio === null || ratio === undefined) return '-'
  const percent = ratio * 100
  return `${percent.toFixed(percent > 0 && percent < 10 ? 1 : 0)}%`
}

export function relativeTime(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return '-'
  const seconds = Math.round((new Date(iso).getTime() - now) / 1000)
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ['year', 31_536_000],
    ['month', 2_592_000],
    ['week', 604_800],
    ['day', 86_400],
    ['hour', 3_600],
    ['minute', 60],
  ]
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size) return relativeFormatter.format(Math.round(seconds / size), unit)
  }
  return 'just now'
}

export function shortDate(iso: string): string {
  return shortDateFormatter.format(new Date(iso))
}

export function fullDate(iso: string): string {
  return fullDateFormatter.format(new Date(iso))
}

export function plural(count: number, one: string, many = `${one}s`): string {
  return `${formatNumber(count)} ${count === 1 ? one : many}`
}

export function basename(path: string): string {
  return path.slice(path.lastIndexOf('/') + 1)
}

export function dirname(path: string): string {
  const index = path.lastIndexOf('/')
  return index === -1 ? '' : path.slice(0, index + 1)
}
