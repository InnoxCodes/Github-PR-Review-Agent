import { motion } from 'framer-motion'
import { Database, KeyRound, LoaderCircle, Trash2 } from 'lucide-react'
import { forwardRef } from 'react'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { cn } from '@/lib/cn'
import { useSampleData } from '@/lib/hooks'
import type { Health } from '@/lib/types'

interface SetupNoticeProps {
  health: Health | undefined
  highlight: boolean
}

export const SetupNotice = forwardRef<HTMLDivElement, SetupNoticeProps>(function SetupNotice({ health, highlight }, ref) {
  const { load, clear } = useSampleData()
  if (!health || health.llm.configured) {
    return null
  }

  return (
    <motion.div ref={ref} animate={highlight ? { scale: [1, 1.015, 1] } : undefined} transition={{ duration: 0.5 }}>
      <Card className={cn('overflow-hidden transition-shadow duration-500', highlight && 'shadow-glow')}>
        <div className="grid gap-6 p-6 md:grid-cols-[1fr_auto] md:items-center">
          <div className="flex items-start gap-4">
            <span className="grid size-10 shrink-0 place-items-center rounded-xl border border-warning/30 bg-warning-soft text-warning-text">
              <KeyRound className="size-5" aria-hidden />
            </span>
            <div className="min-w-0">
              <h2 className="font-mono text-[15px] font-semibold text-fg">Connect an LLM to run live reviews</h2>
              <p className="mt-1 text-sm leading-relaxed text-fg-muted">
                Add your key to <code className="rounded bg-muted px-1 font-mono text-[13px] text-fg-2">backend/.env</code> and restart
                the API. Until then, explore the dashboard with clearly labelled sample reviews, hand-written, not model output.
              </p>
              <pre className="mt-3 overflow-x-auto rounded-lg border border-line bg-sunken px-3 py-2 font-mono text-[13px] text-fg-2 scrollbar-thin">
                ANTHROPIC_API_KEY=sk-ant-…
              </pre>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 md:flex-col">
            {health.sample_data_loaded ? (
              <Button variant="outline" onClick={() => clear.mutate()} disabled={clear.isPending}>
                {clear.isPending ? <LoaderCircle className="spin-slow size-4" aria-hidden /> : <Trash2 className="size-4" aria-hidden />}
                Remove sample data
              </Button>
            ) : (
              <Button variant="primary" onClick={() => load.mutate()} disabled={load.isPending}>
                {load.isPending ? <LoaderCircle className="spin-slow size-4" aria-hidden /> : <Database className="size-4" aria-hidden />}
                Load sample data
              </Button>
            )}
          </div>
        </div>
      </Card>
    </motion.div>
  )
})
