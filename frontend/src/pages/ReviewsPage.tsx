import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { CloudOff, Inbox, ScanSearch, Search, SearchX } from 'lucide-react'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { ReviewRow } from '@/components/review/ReviewRow'
import { buttonClasses } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { SegmentedControl } from '@/components/ui/SegmentedControl'
import { Skeleton } from '@/components/ui/Skeleton'
import { api, queryKeys } from '@/lib/api'
import { isActive } from '@/lib/meta'
import { listContainer } from '@/lib/motion'

type StatusTab = 'all' | 'running' | 'completed' | 'failed'

export default function ReviewsPage() {
  const [params, setParams] = useSearchParams()
  const repository = params.get('repository') ?? ''
  const [status, setStatus] = useState<StatusTab>('all')
  const [search, setSearch] = useState('')

  const reviews = useQuery({
    queryKey: queryKeys.reviews({ repository, limit: 200 }),
    queryFn: () => api.listReviews({ repository: repository || undefined, limit: 200 }),
    refetchInterval: (query) => (query.state.data?.some((review) => isActive(review.status)) ? 3000 : false),
  })
  const repos = useQuery({ queryKey: queryKeys.repos, queryFn: api.listRepos })

  const all = reviews.data ?? []
  const needle = search.trim().toLowerCase()
  const filtered = all
    .filter((review) => (status === 'all' ? true : status === 'running' ? isActive(review.status) : review.status === status))
    .filter(
      (review) =>
        !needle ||
        `${review.owner}/${review.repo}#${review.pr_number} ${review.pr_title ?? ''} ${review.pr_author ?? ''}`.toLowerCase().includes(needle),
    )

  const repoOptions = repos.data?.map((repo) => repo.full_name) ?? []
  if (repository && !repoOptions.some((name) => name.toLowerCase() === repository.toLowerCase())) repoOptions.unshift(repository)

  return (
    <div className="mx-auto max-w-5xl space-y-6 px-5 py-8 sm:py-10">
      <PageHeader
        eyebrow="History"
        title="Reviews"
        description="Every pull request ReviewMind has reviewed, newest first."
        actions={
          <Link to="/" className={buttonClasses('primary')}>
            <ScanSearch className="size-4" aria-hidden /> New review
          </Link>
        }
      />

      <div className="flex flex-col gap-3 md:flex-row md:items-center">
        <SegmentedControl
          label="Filter by status"
          value={status}
          onChange={setStatus}
          options={[
            { value: 'all', label: 'All', count: all.length },
            { value: 'running', label: 'Running', count: all.filter((review) => isActive(review.status)).length },
            { value: 'completed', label: 'Completed', count: all.filter((review) => review.status === 'completed').length },
            { value: 'failed', label: 'Failed', count: all.filter((review) => review.status === 'failed').length },
          ]}
          className="overflow-x-auto"
        />
        <div className="flex flex-1 flex-col gap-2 sm:flex-row md:justify-end">
          <label className="relative block sm:w-72">
            <span className="sr-only">Search reviews</span>
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-fg-subtle" aria-hidden />
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search title, repo or author"
              className="h-9 w-full rounded-lg border border-line bg-surface pl-9 pr-3 text-sm text-fg placeholder:text-fg-subtle transition-[border-color,box-shadow] focus:border-accent/60 focus:shadow-glow focus-visible:outline-none"
            />
          </label>
          <label htmlFor="repo-filter" className="sr-only">
            Filter by repository
          </label>
          <select
            id="repo-filter"
            value={repository}
            onChange={(event) => setParams(event.target.value ? { repository: event.target.value } : {})}
            className="h-9 cursor-pointer rounded-lg border border-line bg-surface px-3 text-sm text-fg-2 transition-colors hover:border-line-strong"
          >
            <option value="">All repositories</option>
            {repoOptions.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <Card className="p-2">
        {reviews.isLoading ? (
          <ul className="space-y-1 p-1" aria-busy="true">
            {Array.from({ length: 6 }, (_, index) => (
              <li key={index} className="flex items-center gap-4 px-2 py-3">
                <Skeleton className="size-11 rounded-full" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-3 w-40" />
                  <Skeleton className="h-4 w-2/3" />
                </div>
                <Skeleton className="hidden h-4 w-28 sm:block" />
              </li>
            ))}
          </ul>
        ) : reviews.isError ? (
          <EmptyState icon={CloudOff} title="Can't reach the API" description={reviews.error.message} />
        ) : all.length === 0 ? (
          <EmptyState
            icon={Inbox}
            title="No reviews yet"
            description="Paste a pull request URL on the home page to run your first review."
            action={
              <Link to="/" className={buttonClasses('primary', 'sm')}>
                Start a review
              </Link>
            }
          />
        ) : filtered.length === 0 ? (
          <EmptyState icon={SearchX} title="No reviews match" description="Try a different status, repository or search term." />
        ) : (
          <motion.ul key={`${status}-${repository}`} variants={listContainer} initial="hidden" animate="show" className="space-y-0.5">
            {filtered.map((review) => (
              <ReviewRow key={review.id} review={review} />
            ))}
          </motion.ul>
        )}
      </Card>
    </div>
  )
}
