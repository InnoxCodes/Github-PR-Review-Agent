import { motion } from 'framer-motion'
import { CircleDashed, CircleSlash, CircleX, LoaderCircle } from 'lucide-react'
import type { FileState } from '@/lib/types'

export function FileStateIcon({ state }: { state: FileState }) {
  switch (state) {
    case 'pending':
      return <CircleDashed className="size-5 text-fg-subtle" aria-label="Waiting" />
    case 'reviewing':
      return <LoaderCircle className="spin-slow size-5 text-accent-text" aria-label="Reviewing" />
    case 'failed':
      return <CircleX className="size-5 text-critical-text" aria-label="Failed" />
    case 'skipped':
      return <CircleSlash className="size-5 text-fg-subtle" aria-label="Skipped" />
    case 'done':
      return (
        <svg
          viewBox="0 0 24 24"
          role="img"
          aria-label="Reviewed"
          className="size-5 text-good-text"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <motion.circle cx="12" cy="12" r="9.25" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.35, ease: 'easeOut' }} />
          <motion.path
            d="m8 12.5 2.6 2.6L16 9.5"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 0.3, delay: 0.25, ease: 'easeOut' }}
          />
        </svg>
      )
  }
}
