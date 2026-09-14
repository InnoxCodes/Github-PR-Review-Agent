import { AnimatePresence, motion } from 'framer-motion'
import { Check, Copy } from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { cn } from '@/lib/cn'

interface CopyButtonProps {
  text: string
  label?: string
  className?: string
  onCopied?: () => void
}

export function CopyButton({ text, label = 'Copy', className, onCopied }: CopyButtonProps) {
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!copied) return
    const timer = setTimeout(() => setCopied(false), 1600)
    return () => clearTimeout(timer)
  }, [copied])

  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      onCopied?.()
    } catch {
      toast.error('Clipboard access was blocked by the browser.')
    }
  }

  return (
    <button
      type="button"
      onClick={copy}
      className={cn(
        'inline-flex h-7 items-center gap-1.5 rounded-md border border-line bg-surface/80 px-2 text-xs font-medium text-fg-muted backdrop-blur',
        'transition-colors duration-200 hover:border-line-strong hover:text-fg',
        copied && 'border-accent/40 text-accent-text',
        className,
      )}
    >
      <span className="relative grid size-3.5 place-items-center">
        <AnimatePresence initial={false} mode="popLayout">
          <motion.span
            key={copied ? 'done' : 'idle'}
            initial={{ opacity: 0, scale: 0.4, rotate: -30 }}
            animate={{ opacity: 1, scale: 1, rotate: 0 }}
            exit={{ opacity: 0, scale: 0.4 }}
            transition={{ type: 'spring', stiffness: 500, damping: 28 }}
            className="absolute"
          >
            {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
          </motion.span>
        </AnimatePresence>
      </span>
      <span aria-live="polite">{copied ? 'Copied' : label}</span>
    </button>
  )
}
