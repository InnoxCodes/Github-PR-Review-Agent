import { ChevronRight, CircleSlash, FileCode2 } from 'lucide-react'
import { Fragment, useEffect, useMemo, useState } from 'react'
import { RichText } from '@/components/ui/RichText'
import { basename, dirname, formatNumber } from '@/lib/format'
import { cn } from '@/lib/cn'
import { usePrefersReducedMotion } from '@/lib/hooks'
import { SEVERITIES, SEVERITY_META, SKIP_REASON_LABEL } from '@/lib/meta'
import type { Issue, ReviewFileDetail } from '@/lib/types'
import { useHunkTokens } from '@/lib/useHighlight'
import { CategoryTag } from './CategoryTag'

interface DiffViewerProps {
  reviewId: string
  files: ReviewFileDetail[]
  issues: Issue[]
  selectedIssueId: string | null
  onSelectIssue: (id: string) => void
  /** Scroll the selected finding's thread into view (off when it was clicked in the diff itself). */
  autoScroll: boolean
}

export function DiffViewer({ reviewId, files, issues, selectedIssueId, onSelectIssue, autoScroll }: DiffViewerProps) {
  const reduceMotion = usePrefersReducedMotion()
  const selected = issues.find((issue) => issue.id === selectedIssueId) ?? null

  const issuesByFile = useMemo(() => {
    const map = new Map<number, Issue[]>()
    for (const issue of issues) map.set(issue.file_id, [...(map.get(issue.file_id) ?? []), issue])
    return map
  }, [issues])

  useEffect(() => {
    if (!selectedIssueId || !autoScroll) return
    // Let an expanding file render before scrolling to its thread.
    const frame = requestAnimationFrame(() =>
      document
        .getElementById(`thread-${selectedIssueId}`)
        ?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'center' }),
    )
    return () => cancelAnimationFrame(frame)
  }, [selectedIssueId, autoScroll, reduceMotion])

  return (
    <div className="space-y-4">
      {files.map((file) => (
        <FileDiff
          key={file.id}
          reviewId={reviewId}
          file={file}
          issues={issuesByFile.get(file.id) ?? []}
          selected={selected?.file_id === file.id ? selected : null}
          onSelectIssue={onSelectIssue}
        />
      ))}
    </div>
  )
}

const STATUS_BADGE: Record<string, string> = {
  added: 'bg-accent-soft text-accent-text',
  removed: 'bg-critical-soft text-critical-text',
  renamed: 'bg-info-soft text-info-text',
}

interface FileDiffProps {
  reviewId: string
  file: ReviewFileDetail
  issues: Issue[]
  selected: Issue | null
  onSelectIssue: (id: string) => void
}

function FileDiff({ reviewId, file, issues, selected, onSelectIssue }: FileDiffProps) {
  const skipped = file.state === 'skipped'
  const [open, setOpen] = useState(!skipped)
  const expanded = open || selected !== null
  const tokens = useHunkTokens(`${reviewId}:${file.id}`, file.hunks, file.language, expanded && !skipped)

  const { anchoredAt, threadsAfter } = useMemo(() => {
    const anchoredAt = new Map<number, Issue[]>()
    const threadsAfter = new Map<number, Issue[]>()
    for (const issue of issues) {
      anchoredAt.set(issue.line_number, [...(anchoredAt.get(issue.line_number) ?? []), issue])
      const last = issue.end_line ?? issue.line_number
      threadsAfter.set(last, [...(threadsAfter.get(last) ?? []), issue])
    }
    return { anchoredAt, threadsAfter }
  }, [issues])

  const range = selected ? [selected.line_number, selected.end_line ?? selected.line_number] : null

  return (
    <section
      id={`file-${file.id}`}
      aria-label={file.filename}
      className="scroll-mt-4 overflow-hidden rounded-xl border border-line bg-surface shadow-card"
    >
      <header className="flex items-center gap-2.5 border-b border-line bg-raised/50 px-2.5 py-2">
        <button
          type="button"
          onClick={() => setOpen(!expanded)}
          aria-expanded={expanded}
          aria-controls={`file-body-${file.id}`}
          aria-label={expanded ? `Collapse ${file.filename}` : `Expand ${file.filename}`}
          className="grid size-7 shrink-0 place-items-center rounded-md text-fg-muted transition-colors hover:bg-muted hover:text-fg"
        >
          <ChevronRight className={cn('size-4 transition-transform duration-200', expanded && 'rotate-90')} />
        </button>
        <FileCode2 className="size-4 shrink-0 text-fg-subtle" aria-hidden />
        <span className="min-w-0 truncate font-mono text-[13px]">
          <span className="text-fg-muted">{dirname(file.filename)}</span>
          <span className="font-medium text-fg">{basename(file.filename)}</span>
        </span>
        {STATUS_BADGE[file.git_status] && (
          <span className={cn('hidden rounded px-1.5 py-0.5 text-xs font-medium capitalize sm:inline', STATUS_BADGE[file.git_status])}>
            {file.git_status}
          </span>
        )}
        <span className="ml-auto flex shrink-0 items-center gap-2">
          {SEVERITIES.map((severity) => {
            const count = issues.filter((issue) => issue.severity === severity).length
            if (!count) return null
            const Icon = SEVERITY_META[severity].icon
            return (
              <span key={severity} className={cn('inline-flex items-center gap-1 text-xs font-medium', SEVERITY_META[severity].text)}>
                <Icon className="size-3.5" aria-hidden />
                <span className="tabular">{count}</span>
                <span className="sr-only">{SEVERITY_META[severity].label}</span>
              </span>
            )
          })}
          <span className="tabular font-mono text-xs">
            <span className="text-diff-add-sign">+{formatNumber(file.additions)}</span>{' '}
            <span className="text-diff-del-sign">−{formatNumber(file.deletions)}</span>
          </span>
        </span>
      </header>

      {skipped ? (
        <div className="flex items-center gap-2 px-4 py-3 text-[13px] text-fg-muted">
          <CircleSlash className="size-4 text-fg-subtle" aria-hidden />
          Not reviewed, {SKIP_REASON_LABEL[file.skip_reason ?? ''] ?? file.skip_reason}
        </div>
      ) : (
        expanded && (
          <div id={`file-body-${file.id}`} className="font-mono text-[12.5px] leading-[1.4rem]">
            {file.state === 'failed' && file.error && (
              <div className="border-b border-line bg-critical-soft px-4 py-2 font-sans text-[13px] text-critical-text">{file.error}</div>
            )}
            {file.hunks.map((hunk, hunkIndex) => (
              <Fragment key={hunkIndex}>
                <div className="flex bg-diff-hunk text-diff-hunk-text">
                  <span aria-hidden className="w-[5.75rem] shrink-0 select-none text-center opacity-60">
                    ⋯
                  </span>
                  <span className="min-w-0 truncate px-2 py-0.5">
                    @@ -{hunk.old_start},{hunk.old_lines} +{hunk.new_start},{hunk.new_lines} @@
                    <span className="text-fg-muted"> {hunk.section}</span>
                  </span>
                </div>
                {hunk.lines.map((line, lineIndex) => {
                  const newLine = line.type === 'delete' ? null : line.new_line
                  const anchored = newLine !== null ? anchoredAt.get(newLine) : undefined
                  const threads = newLine !== null ? threadsAfter.get(newLine) : undefined
                  const inRange = range !== null && newLine !== null && newLine >= range[0] && newLine <= range[1]
                  const topSeverity = anchored?.map((issue) => issue.severity).sort((a, b) => SEVERITY_META[a].rank - SEVERITY_META[b].rank)[0]
                  const lineTokens = tokens?.[hunkIndex]?.[lineIndex]

                  return (
                    <Fragment key={lineIndex}>
                      <div
                        className={cn(
                          'relative flex',
                          line.type === 'add' && 'bg-diff-add',
                          line.type === 'delete' && 'bg-diff-del',
                          inRange && 'bg-accent-soft',
                        )}
                      >
                        {inRange && <span aria-hidden className="absolute inset-y-0 left-0 w-[3px] bg-accent" />}
                        <span
                          aria-hidden
                          className={cn(
                            'w-[2.75rem] shrink-0 select-none pr-2 text-right text-fg-subtle',
                            line.type === 'delete' && 'bg-diff-del-strong',
                          )}
                        >
                          {line.old_line ?? ''}
                        </span>
                        {anchored ? (
                          <button
                            type="button"
                            onClick={() => onSelectIssue(anchored[0].id)}
                            aria-label={`${anchored.length} finding${anchored.length > 1 ? 's' : ''} on line ${newLine}`}
                            className={cn(
                              'relative flex w-[2.75rem] shrink-0 items-center justify-end gap-1 pr-2 text-right text-fg-2 transition-colors hover:bg-muted',
                              line.type === 'add' && 'bg-diff-add-strong',
                            )}
                          >
                            <span className={cn('size-2 shrink-0 rounded-full', topSeverity && SEVERITY_META[topSeverity].dot)} />
                            <span className="tabular">{newLine}</span>
                          </button>
                        ) : (
                          <span
                            aria-hidden
                            className={cn('w-[2.75rem] shrink-0 select-none pr-2 text-right text-fg-subtle', line.type === 'add' && 'bg-diff-add-strong')}
                          >
                            {newLine ?? ''}
                          </span>
                        )}
                        <span
                          aria-hidden
                          className={cn(
                            'w-5 shrink-0 select-none text-center',
                            line.type === 'add' && 'text-diff-add-sign',
                            line.type === 'delete' && 'text-diff-del-sign',
                          )}
                        >
                          {line.type === 'add' ? '+' : line.type === 'delete' ? '−' : ''}
                        </span>
                        <code className="min-w-0 flex-1 whitespace-pre-wrap pr-4 text-fg [overflow-wrap:anywhere]">
                          <span className="sr-only">
                            {line.type === 'add' ? 'Added: ' : line.type === 'delete' ? 'Removed: ' : ''}
                          </span>
                          {lineTokens
                            ? lineTokens.map((token, tokenIndex) => (
                                <span key={tokenIndex} className="shiki-token" style={token.style}>
                                  {token.content}
                                </span>
                              ))
                            : line.content}
                          {line.content === '' && ' '}
                        </code>
                      </div>
                      {threads?.map((issue) => (
                        <InlineThread key={issue.id} issue={issue} selected={issue.id === selected?.id} onSelect={onSelectIssue} />
                      ))}
                    </Fragment>
                  )
                })}
              </Fragment>
            ))}
          </div>
        )
      )}
    </section>
  )
}

function InlineThread({ issue, selected, onSelect }: { issue: Issue; selected: boolean; onSelect: (id: string) => void }) {
  const meta = SEVERITY_META[issue.severity]
  const Icon = meta.icon
  return (
    <div id={`thread-${issue.id}`} className="scroll-mt-24 border-y border-line bg-sunken px-3 py-2 font-sans">
      <button
        type="button"
        onClick={() => onSelect(issue.id)}
        className={cn(
          'flex w-full max-w-3xl items-start gap-3 rounded-lg border bg-surface px-3 py-2.5 text-left transition-[border-color,box-shadow] duration-200',
          selected ? 'border-accent/50 shadow-glow' : 'border-line hover:border-line-strong',
          issue.status !== 'open' && 'opacity-70',
        )}
      >
        <Icon className={cn('mt-0.5 size-4 shrink-0', meta.text)} aria-label={meta.label} />
        <span className="min-w-0 flex-1">
          <span className="block text-[13px] font-semibold text-fg">{issue.title}</span>
          <span className="mt-0.5 line-clamp-2 block text-[13px] leading-relaxed text-fg-muted">
            <RichText text={issue.comment} />
          </span>
        </span>
        <CategoryTag category={issue.category} className="hidden sm:inline-flex" />
      </button>
    </div>
  )
}
