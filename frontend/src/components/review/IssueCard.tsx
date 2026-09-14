import { AnimatePresence, motion } from 'framer-motion'
import { Ban, Check, ChevronDown, Flag, Undo2, Wand2 } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { CopyButton } from '@/components/ui/CopyButton'
import { Kbd } from '@/components/ui/Kbd'
import { RichText } from '@/components/ui/RichText'
import { cn } from '@/lib/cn'
import { ISSUE_STATUS_META, SEVERITY_META } from '@/lib/meta'
import { exitFast, spring } from '@/lib/motion'
import type { Issue, IssueStatus } from '@/lib/types'
import { CategoryTag } from './CategoryTag'
import { CodeBlock } from './CodeBlock'
import { ConfidenceMeter } from './ConfidenceMeter'
import { SeverityBadge } from './SeverityBadge'

interface IssueCardProps {
  issue: Issue
  language: string
  selected: boolean
  onSelect: () => void
  onStatus: (status: IssueStatus) => void
}

export function IssueCard({ issue, language, selected, onSelect, onStatus }: IssueCardProps) {
  const [fixOpen, setFixOpen] = useState(false)
  const meta = SEVERITY_META[issue.severity]
  const resolved = issue.status !== 'open'
  const statusMeta = ISSUE_STATUS_META[issue.status]
  const StatusIcon = statusMeta.icon
  const showFix = fixOpen || selected

  return (
    <motion.article
      layout="position"
      id={`issue-card-${issue.id}`}
      aria-current={selected ? 'true' : undefined}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: 36, scale: 0.97, transition: exitFast }}
      transition={spring}
      onClick={onSelect}
      className={cn(
        'relative cursor-pointer overflow-hidden rounded-xl border border-l-[3px] bg-surface p-4',
        'transition-[background-color,border-color,box-shadow] duration-200',
        meta.border,
        selected
          ? 'border-y-line-strong border-r-line-strong bg-raised shadow-pop'
          : 'border-y-line border-r-line hover:bg-raised/60',
      )}
    >
      <AnimatePresence>
        {issue.status === 'accepted' && (
          <motion.span
            key="accepted"
            aria-hidden
            initial={{ opacity: 0, scale: 0.3, rotate: -30 }}
            animate={{ opacity: 1, scale: 1, rotate: 0 }}
            exit={{ opacity: 0, scale: 0.6 }}
            transition={{ type: 'spring', stiffness: 520, damping: 22 }}
            className="absolute right-3 top-3 grid size-7 place-items-center rounded-full bg-good text-white shadow-[0_0_0_4px_var(--rm-good-soft)]"
          >
            <Check className="size-4" strokeWidth={3} />
          </motion.span>
        )}
      </AnimatePresence>

      <div className="flex flex-wrap items-center gap-1.5 pr-8">
        <SeverityBadge severity={issue.severity} pulse={issue.severity === 'critical' && !resolved} />
        <CategoryTag category={issue.category} />
        <ConfidenceMeter confidence={issue.confidence} className="ml-1" />
      </div>

      <h3 className="mt-2.5 font-sans text-[15px] font-semibold leading-snug tracking-normal text-fg">
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation()
            onSelect()
          }}
          className="text-left"
        >
          {issue.title}
        </button>
      </h3>
      <p className="mt-1 truncate font-mono text-xs text-fg-muted">
        {issue.filename}:{issue.line_number}
        {issue.end_line ? `–${issue.end_line}` : ''}
      </p>
      <p className={cn('mt-2.5 text-sm leading-relaxed', resolved ? 'text-fg-muted' : 'text-fg-2')}>
        <RichText text={issue.comment} />
      </p>

      {issue.suggested_fix && (
        <div className="mt-3 overflow-hidden rounded-lg border border-line bg-sunken" onClick={(event) => event.stopPropagation()}>
          <div className="flex items-center justify-between gap-2 px-2.5 py-1.5">
            <button
              type="button"
              aria-expanded={showFix}
              onClick={() => setFixOpen((open) => !open)}
              className="inline-flex h-7 items-center gap-1.5 text-xs font-medium text-fg-muted transition-colors hover:text-fg"
            >
              <Wand2 className="size-3.5 text-accent-text" aria-hidden />
              Suggested fix
              <ChevronDown className={cn('size-3.5 transition-transform duration-200', showFix && 'rotate-180')} aria-hidden />
            </button>
            <CopyButton text={issue.suggested_fix} />
          </div>
          {showFix && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.2 }} className="border-t border-line">
              <CodeBlock code={issue.suggested_fix} language={language} />
            </motion.div>
          )}
        </div>
      )}

      <div className="mt-3.5 flex flex-wrap items-center gap-1.5" onClick={(event) => event.stopPropagation()}>
        {resolved ? (
          <>
            <span className={cn('inline-flex h-8 items-center gap-1.5 text-[13px] font-medium', statusMeta.text)}>
              <StatusIcon className="size-4" aria-hidden />
              {statusMeta.label}
            </span>
            <ActionButton icon={<Undo2 />} label="Reopen" hotkey="u" showHotkey={selected} onClick={() => onStatus('open')} className="ml-auto" />
          </>
        ) : (
          <>
            <ActionButton icon={<Check />} label="Accept" hotkey="a" showHotkey={selected} tone="good" onClick={() => onStatus('accepted')} />
            <ActionButton icon={<Ban />} label="Dismiss" hotkey="d" showHotkey={selected} onClick={() => onStatus('dismissed')} />
            <ActionButton
              icon={<Flag />}
              label="False positive"
              hotkey="f"
              showHotkey={selected}
              tone="warning"
              onClick={() => onStatus('false_positive')}
            />
          </>
        )}
      </div>
    </motion.article>
  )
}

interface ActionButtonProps {
  icon: ReactNode
  label: string
  hotkey: string
  showHotkey: boolean
  tone?: 'good' | 'warning'
  onClick: () => void
  className?: string
}

function ActionButton({ icon, label, hotkey, showHotkey, tone, onClick, className }: ActionButtonProps) {
  return (
    <motion.button
      type="button"
      whileTap={{ scale: 0.94 }}
      onClick={onClick}
      aria-keyshortcuts={hotkey}
      className={cn(
        'inline-flex h-8 items-center gap-1.5 rounded-md border border-line bg-surface px-2.5 text-[13px] font-medium text-fg-2',
        'transition-colors duration-200 hover:border-line-strong hover:text-fg [&_svg]:size-3.5',
        tone === 'good' && 'hover:border-good/40 hover:bg-good-soft hover:text-good-text',
        tone === 'warning' && 'hover:border-warning/40 hover:bg-warning-soft hover:text-warning-text',
        !tone && 'hover:bg-muted',
        className,
      )}
    >
      {icon}
      {label}
      {showHotkey && <Kbd className="ml-0.5 h-[18px] min-w-[18px]">{hotkey}</Kbd>}
    </motion.button>
  )
}
