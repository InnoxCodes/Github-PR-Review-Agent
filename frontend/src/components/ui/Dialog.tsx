import { AnimatePresence, motion } from 'framer-motion'
import { X } from 'lucide-react'
import { useEffect, useId, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '@/lib/cn'
import { exitFast, spring } from '@/lib/motion'

interface DialogProps {
  open: boolean
  onClose: () => void
  title: ReactNode
  description?: ReactNode
  children: ReactNode
  footer?: ReactNode
  className?: string
  /** Keep the title for screen readers but render a custom layout (command palette). */
  hideHeader?: boolean
  placement?: 'center' | 'top'
}

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  className,
  hideHeader = false,
  placement = 'center',
}: DialogProps) {
  const panelRef = useRef<HTMLDivElement>(null)
  const onCloseRef = useRef(onClose)
  const titleId = useId()
  const descriptionId = useId()

  useEffect(() => {
    onCloseRef.current = onClose
  })

  useEffect(() => {
    if (!open) return
    const previouslyFocused = document.activeElement as HTMLElement | null
    const focusables = () => Array.from(panelRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? [])

    const frame = requestAnimationFrame(() => {
      const preferred = panelRef.current?.querySelector<HTMLElement>('[data-autofocus]')
      ;(preferred ?? focusables()[0])?.focus()
    })

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onCloseRef.current()
        return
      }
      if (event.key !== 'Tab') return
      const items = focusables()
      if (items.length === 0) return
      const first = items[0]
      const last = items[items.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', onKeyDown)
    document.body.dataset.modalOpen = 'true'
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      cancelAnimationFrame(frame)
      document.removeEventListener('keydown', onKeyDown)
      delete document.body.dataset.modalOpen
      document.body.style.overflow = overflow
      previouslyFocused?.focus()
    }
  }, [open])

  return createPortal(
    <AnimatePresence>
      {open && (
        <div
          className={cn(
            'fixed inset-0 z-50 flex justify-center p-4',
            placement === 'center' ? 'items-center' : 'items-start pt-[12vh]',
          )}
        >
          <motion.div
            className="absolute inset-0 bg-[rgb(3_6_14/0.62)] backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1, transition: { duration: 0.2 } }}
            exit={{ opacity: 0, transition: exitFast }}
            onClick={onClose}
          />
          <motion.div
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            aria-describedby={description ? descriptionId : undefined}
            className={cn(
              'relative w-full max-w-lg overflow-hidden rounded-2xl border border-line-strong bg-surface shadow-pop',
              className,
            )}
            initial={{ opacity: 0, y: 16, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1, transition: spring }}
            exit={{ opacity: 0, y: 8, scale: 0.98, transition: exitFast }}
          >
            {hideHeader ? (
              <h2 id={titleId} className="sr-only">
                {title}
              </h2>
            ) : (
              <div className="flex items-start justify-between gap-4 px-6 pt-5">
                <div>
                  <h2 id={titleId} className="text-base font-semibold text-fg">
                    {title}
                  </h2>
                  {description && (
                    <p id={descriptionId} className="mt-1 text-sm text-fg-muted">
                      {description}
                    </p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={onClose}
                  aria-label="Close dialog"
                  className="-mr-2 -mt-1 grid size-9 place-items-center rounded-lg text-fg-muted transition-colors hover:bg-muted hover:text-fg"
                >
                  <X className="size-4" />
                </button>
              </div>
            )}
            <div className={cn(!hideHeader && 'px-6 pb-6 pt-4')}>{children}</div>
            {footer && (
              <div className="flex items-center justify-end gap-2 border-t border-line bg-raised/60 px-6 py-3.5">{footer}</div>
            )}
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  )
}
