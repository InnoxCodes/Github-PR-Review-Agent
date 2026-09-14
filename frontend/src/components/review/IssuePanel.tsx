import { AnimatePresence, LayoutGroup } from 'framer-motion'
import { ArrowUpDown, BadgeCheck, CheckCheck, SearchX } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { Kbd } from '@/components/ui/Kbd'
import { SegmentedControl } from '@/components/ui/SegmentedControl'
import { cn } from '@/lib/cn'
import { CATEGORIES, CATEGORY_META, SEVERITIES, SEVERITY_META } from '@/lib/meta'
import type { Issue, IssueStatus, Severity } from '@/lib/types'
import { DEFAULT_FILTERS, matchesStatus, type IssueFilters, type StatusFilter } from './issueFilters'
import { IssueCard } from './IssueCard'

interface IssuePanelProps {
  issues: Issue[]
  visible: Issue[]
  filters: IssueFilters
  onFiltersChange: (filters: IssueFilters) => void
  selectedId: string | null
  onSelect: (id: string) => void
  onStatus: (issue: Issue, status: IssueStatus) => void
  languageFor: (fileId: number) => string
  /** Scroll the list to the selected card (off when the selection came from this panel). */
  autoScroll: boolean
  className?: string
}

export function IssuePanel({
  issues,
  visible,
  filters,
  onFiltersChange,
  selectedId,
  onSelect,
  onStatus,
  languageFor,
  autoScroll,
  className,
}: IssuePanelProps) {
  const listRef = useRef<HTMLDivElement>(null)
  const openCount = issues.filter((issue) => issue.status === 'open').length
  const inStatus = issues.filter((issue) => matchesStatus(issue.status, filters.status))
  const narrowed = filters.severities.length > 0 || filters.category !== 'all'

  useEffect(() => {
    if (!selectedId || !autoScroll) return
    const container = listRef.current
    const card = document.getElementById(`issue-card-${selectedId}`)
    if (!container || !card || container.scrollHeight <= container.clientHeight) return
    // Scroll only this list. scrollIntoView would also move the window and fight the diff's own scroll.
    const bounds = container.getBoundingClientRect()
    const rect = card.getBoundingClientRect()
    const offset = rect.top < bounds.top ? rect.top - bounds.top - 12 : rect.bottom > bounds.bottom ? rect.bottom - bounds.bottom + 12 : 0
    if (offset) container.scrollBy({ top: offset, behavior: 'smooth' })
  }, [selectedId, autoScroll])

  function toggleSeverity(severity: Severity) {
    const active = filters.severities.includes(severity)
    onFiltersChange({
      ...filters,
      severities: active ? filters.severities.filter((item) => item !== severity) : [...filters.severities, severity],
    })
  }

  return (
    <section aria-label="Findings" className={cn('flex min-h-0 flex-col rounded-2xl border border-line bg-surface shadow-card', className)}>
      <header className="space-y-3 border-b border-line p-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="font-mono text-[15px] font-semibold text-fg">
            Findings <span className="tabular ml-1 font-sans text-fg-muted">{visible.length}</span>
          </h2>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => onFiltersChange({ ...filters, sort: filters.sort === 'severity' ? 'location' : 'severity' })}
          >
            <ArrowUpDown className="size-3.5" aria-hidden />
            By {filters.sort}
          </Button>
        </div>

        <SegmentedControl
          label="Finding status"
          value={filters.status}
          onChange={(status: StatusFilter) => onFiltersChange({ ...filters, status })}
          options={[
            { value: 'open', label: 'Open', count: openCount },
            { value: 'resolved', label: 'Resolved', count: issues.length - openCount },
            { value: 'all', label: 'All', count: issues.length },
          ]}
          className="flex w-full [&>button]:flex-1 [&>button]:justify-center"
        />

        <div className="flex flex-wrap items-center gap-1.5">
          {SEVERITIES.map((severity) => {
            const meta = SEVERITY_META[severity]
            const Icon = meta.icon
            const active = filters.severities.includes(severity)
            const count = inStatus.filter((issue) => issue.severity === severity).length
            return (
              <button
                key={severity}
                type="button"
                aria-pressed={active}
                onClick={() => toggleSeverity(severity)}
                className={cn(
                  'inline-flex h-7 items-center gap-1.5 rounded-md border px-2 text-xs font-medium transition-colors duration-200',
                  active
                    ? cn(meta.soft, meta.text, 'border-transparent')
                    : 'border-line text-fg-muted hover:border-line-strong hover:text-fg',
                )}
              >
                <Icon className={cn('size-3.5', meta.text)} aria-hidden />
                {meta.label}
                <span className="tabular opacity-80">{count}</span>
              </button>
            )
          })}
          <label htmlFor="category-filter" className="sr-only">
            Filter by category
          </label>
          <select
            id="category-filter"
            value={filters.category}
            onChange={(event) => onFiltersChange({ ...filters, category: event.target.value as IssueFilters['category'] })}
            className="ml-auto h-7 cursor-pointer rounded-md border border-line bg-surface px-2 text-xs text-fg-2 transition-colors hover:border-line-strong"
          >
            <option value="all">All categories</option>
            {CATEGORIES.map((category) => (
              <option key={category} value={category}>
                {CATEGORY_META[category].label}
              </option>
            ))}
          </select>
        </div>
      </header>

      <div ref={listRef} className="min-h-0 flex-1 overflow-y-auto p-3 scrollbar-thin">
        {visible.length === 0 ? (
          issues.length === 0 ? (
            <EmptyState
              icon={BadgeCheck}
              title="No issues found"
              description="ReviewMind didn't flag anything in the reviewed files. It can't run the code, so this is a good sign — not a guarantee."
            />
          ) : narrowed ? (
            <EmptyState
              icon={SearchX}
              title="No findings match these filters"
              description="Try another severity or category."
              action={
                <Button size="sm" onClick={() => onFiltersChange({ ...DEFAULT_FILTERS, status: filters.status, sort: filters.sort })}>
                  Clear filters
                </Button>
              }
            />
          ) : (
            <EmptyState
              icon={CheckCheck}
              title="Everything's triaged"
              description="No open findings left. Switch to Resolved to revisit your decisions."
              action={
                <Button size="sm" onClick={() => onFiltersChange({ ...filters, status: 'resolved' })}>
                  Show resolved
                </Button>
              }
            />
          )
        ) : (
          <LayoutGroup>
            <div className="space-y-2.5">
              <AnimatePresence initial={false}>
                {visible.map((issue) => (
                  <IssueCard
                    key={issue.id}
                    issue={issue}
                    language={languageFor(issue.file_id)}
                    selected={issue.id === selectedId}
                    onSelect={() => onSelect(issue.id)}
                    onStatus={(status) => onStatus(issue, status)}
                  />
                ))}
              </AnimatePresence>
            </div>
          </LayoutGroup>
        )}
      </div>

      <footer className="hidden flex-wrap items-center gap-x-3 gap-y-1 border-t border-line px-4 py-2.5 text-xs text-fg-muted lg:flex">
        <span className="inline-flex items-center gap-1">
          <Kbd>j</Kbd>
          <Kbd>k</Kbd> move
        </span>
        <span className="inline-flex items-center gap-1">
          <Kbd>a</Kbd> accept
        </span>
        <span className="inline-flex items-center gap-1">
          <Kbd>d</Kbd> dismiss
        </span>
        <span className="inline-flex items-center gap-1">
          <Kbd>f</Kbd> false +
        </span>
        <span className="ml-auto inline-flex items-center gap-1">
          <Kbd>?</Kbd> all shortcuts
        </span>
      </footer>
    </section>
  )
}
