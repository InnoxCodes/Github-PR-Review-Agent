import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { ArrowRight, Braces, CloudOff, Database, FileDiff, FolderGit2, Inbox, ListChecks, Radar } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { toast } from 'sonner'
import { AnimatedBackground } from '@/components/layout/AnimatedBackground'
import { SetupNotice } from '@/components/layout/SetupNotice'
import { TrackRepoDialog } from '@/components/repos/TrackRepoDialog'
import { PRInput } from '@/components/review/PRInput'
import { ReviewRow } from '@/components/review/ReviewRow'
import { Button, buttonClasses } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { Skeleton } from '@/components/ui/Skeleton'
import { api, queryKeys } from '@/lib/api'
import { cn } from '@/lib/cn'
import { useSampleData } from '@/lib/hooks'
import { isActive } from '@/lib/meta'
import { easeOut, listContainer, riseIn } from '@/lib/motion'

const STEPS = [
  { icon: FileDiff, title: 'Fetch & filter', body: 'Pulls the diff file by file from GitHub and skips lockfiles, generated code and assets.' },
  { icon: Braces, title: 'Structured review', body: 'Splits large files at hunk boundaries. The model must answer in a strict JSON schema.' },
  { icon: ListChecks, title: 'Validate & anchor', body: 'Malformed output is retried with the exact error, and every finding is pinned to a real diff line.' },
  { icon: Radar, title: 'Triage & learn', body: 'Accept, dismiss or flag findings. Every verdict updates the health score and precision analytics.' },
]

export default function HomePage() {
  const [params] = useSearchParams()
  const [trackOpen, setTrackOpen] = useState(false)
  const [highlightSetup, setHighlightSetup] = useState(false)
  const setupRef = useRef<HTMLDivElement>(null)
  const health = useQuery({ queryKey: queryKeys.health, queryFn: api.health })
  const recent = useQuery({
    queryKey: queryKeys.reviews({ limit: 6 }),
    queryFn: () => api.listReviews({ limit: 6 }),
    refetchInterval: (query) => (query.state.data?.some((review) => isActive(review.status)) ? 3000 : false),
  })
  const { load } = useSampleData()
  const configured = health.data?.llm.configured

  useEffect(() => {
    if (!highlightSetup) return
    const timer = setTimeout(() => setHighlightSetup(false), 1600)
    return () => clearTimeout(timer)
  }, [highlightSetup])

  function needsSetup() {
    setHighlightSetup(true)
    setupRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    toast.warning(health.data?.demo ? 'Live reviews are off in this hosted demo' : 'No LLM API key configured', {
      description: health.data?.demo
        ? 'Open a sample review below, or run ReviewMind locally with an API key.'
        : 'Add ANTHROPIC_API_KEY to backend/.env, or explore the sample reviews.',
    })
  }

  return (
    <>
      <section className="relative isolate overflow-hidden border-b border-line">
        <AnimatedBackground />
        <div className="mx-auto flex max-w-4xl flex-col items-center px-5 pb-16 pt-14 text-center sm:pt-20 lg:pb-20 lg:pt-24">
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={easeOut}
            className="inline-flex items-center gap-2 rounded-full border border-line-strong bg-surface/70 px-3 py-1 text-xs text-fg-2 backdrop-blur"
          >
            <span className="relative flex size-2">
              {configured && <span className="absolute inline-flex size-full animate-ping rounded-full bg-accent opacity-60" />}
              <span className={cn('relative inline-flex size-2 rounded-full', configured ? 'bg-accent' : 'bg-warning')} />
            </span>
            {health.isLoading ? (
              'Checking configuration…'
            ) : configured ? (
              <>
                Reviews powered by <span className="font-mono text-fg">{health.data?.llm.model}</span>
              </>
            ) : (
              'Sample mode · add an API key for live reviews'
            )}
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...easeOut, delay: 0.06 }}
            className="mt-6 text-[34px] font-semibold leading-[1.1] tracking-tight text-fg sm:text-5xl lg:text-[56px]"
          >
            Every pull request,
            <br />
            <span className="text-gradient-accent">reviewed line by line.</span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...easeOut, delay: 0.12 }}
            className="mt-5 max-w-xl text-[17px] leading-relaxed text-fg-muted"
          >
            Paste a GitHub PR. ReviewMind reads the diff, flags bugs, security risks and missing tests, and pins every finding to the
            exact line, streaming results as it works.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...easeOut, delay: 0.18 }}
            className="mt-9 w-full max-w-2xl"
          >
            <PRInput initialValue={params.get('pr') ?? ''} llmReady={configured} onNeedsSetup={needsSetup} />
          </motion.div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ ...easeOut, delay: 0.26 }}
            className="mt-5 flex flex-wrap items-center justify-center gap-2"
          >
            <Button variant="ghost" onClick={() => setTrackOpen(true)}>
              <FolderGit2 className="size-4" aria-hidden /> Track a repository
            </Button>
            {health.data && !health.data.sample_data_loaded && (
              <Button variant="ghost" onClick={() => load.mutate()} disabled={load.isPending}>
                <Database className="size-4" aria-hidden /> Explore sample data
              </Button>
            )}
          </motion.div>
        </div>
      </section>

      <div className="mx-auto max-w-5xl space-y-8 px-5 py-10 sm:py-12">
        <SetupNotice ref={setupRef} health={health.data} highlight={highlightSetup} />

        <Card>
          <CardHeader
            title="Recent reviews"
            description="Pick up where you left off."
            action={
              <Link to="/reviews" className={buttonClasses('ghost', 'sm')}>
                View all <ArrowRight className="size-3.5" aria-hidden />
              </Link>
            }
          />
          <div className="p-2 pt-3">
            {recent.isLoading ? (
              <ul className="space-y-1 p-1" aria-busy="true">
                {Array.from({ length: 3 }, (_, index) => (
                  <li key={index} className="flex items-center gap-4 px-2 py-3">
                    <Skeleton className="size-11 rounded-full" />
                    <div className="flex-1 space-y-2">
                      <Skeleton className="h-3 w-40" />
                      <Skeleton className="h-4 w-3/4" />
                    </div>
                  </li>
                ))}
              </ul>
            ) : recent.isError ? (
              <EmptyState icon={CloudOff} title="Can't reach the API" description={recent.error.message} />
            ) : recent.data && recent.data.length > 0 ? (
              <motion.ul variants={listContainer} initial="hidden" animate="show" className="space-y-0.5">
                {recent.data.map((review) => (
                  <ReviewRow key={review.id} review={review} />
                ))}
              </motion.ul>
            ) : (
              <EmptyState
                icon={Inbox}
                title="No PRs reviewed yet"
                description="Paste a pull request URL above to get started, or load the sample reviews to explore the dashboard."
                action={
                  <Button onClick={() => load.mutate()} disabled={load.isPending}>
                    <Database className="size-4" aria-hidden /> Load sample data
                  </Button>
                }
              />
            )}
          </div>
        </Card>

        <section aria-labelledby="how-it-works">
          <h2 id="how-it-works" className="mb-4 font-mono text-xs uppercase tracking-[0.18em] text-fg-muted">
            How it works
          </h2>
          <motion.ol
            variants={listContainer}
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, margin: '-60px' }}
            className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
          >
            {STEPS.map((step, index) => (
              <motion.li key={step.title} variants={riseIn} className="rounded-2xl border border-line bg-surface/60 p-5">
                <div className="flex items-center justify-between">
                  <span className="grid size-9 place-items-center rounded-lg border border-line bg-raised text-accent-text">
                    <step.icon className="size-4" aria-hidden />
                  </span>
                  <span className="font-mono text-xs text-fg-subtle">0{index + 1}</span>
                </div>
                <h3 className="mt-4 text-sm font-semibold text-fg">{step.title}</h3>
                <p className="mt-1.5 text-[13px] leading-relaxed text-fg-muted">{step.body}</p>
              </motion.li>
            ))}
          </motion.ol>
        </section>
      </div>

      <TrackRepoDialog open={trackOpen} onClose={() => setTrackOpen(false)} />
    </>
  )
}
