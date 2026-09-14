import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { ChartColumn, CloudOff, Coins, Database, Flag, GitPullRequest, LoaderCircle, ScanSearch, Timer } from 'lucide-react'
import { useState } from 'react'
import { CategoryBarChart } from '@/components/charts/CategoryBarChart'
import { ChartCard, DataTable } from '@/components/charts/ChartCard'
import { PrecisionBreakdown } from '@/components/charts/PrecisionBreakdown'
import { ScoreTrendChart } from '@/components/charts/ScoreTrendChart'
import { StatTile } from '@/components/charts/StatTile'
import { CategoryLegend, WeeklyFindingsChart, toWeeks } from '@/components/charts/WeeklyFindingsChart'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { SegmentedControl } from '@/components/ui/SegmentedControl'
import { Skeleton } from '@/components/ui/Skeleton'
import { api, queryKeys } from '@/lib/api'
import { cn } from '@/lib/cn'
import { formatCompact, formatCost, formatMinutes, plural, shortDate } from '@/lib/format'
import { useSampleData } from '@/lib/hooks'
import { CATEGORIES, CATEGORY_META } from '@/lib/meta'
import { listContainer, riseIn } from '@/lib/motion'

const RANGES = [
  { value: '7', label: '7 days' },
  { value: '30', label: '30 days' },
  { value: '90', label: '90 days' },
  { value: '365', label: '1 year' },
]

export default function AnalyticsPage() {
  const [range, setRange] = useState('90')
  const days = Number(range)
  const query = useQuery({
    queryKey: queryKeys.analytics(days),
    queryFn: () => api.analytics(days),
    placeholderData: keepPreviousData,
  })
  const { load } = useSampleData()
  const data = query.data

  return (
    <div className="mx-auto max-w-7xl space-y-6 px-5 py-8 sm:py-10">
      <PageHeader eyebrow="Insights" title="Analytics" description="What the reviewer catches, how often developers agree with it, and what it costs." />

      <div className="flex flex-wrap items-center gap-3">
        <SegmentedControl label="Date range" value={range} onChange={setRange} options={RANGES} />
        {query.isFetching && data && (
          <span className="inline-flex items-center gap-1.5 text-xs text-fg-muted" aria-live="polite">
            <LoaderCircle className="spin-slow size-3.5" aria-hidden /> Updating
          </span>
        )}
      </div>

      {query.isLoading ? (
        <AnalyticsSkeleton />
      ) : query.isError ? (
        <Card>
          <EmptyState icon={CloudOff} title="Couldn't load analytics" description={query.error.message} />
        </Card>
      ) : !data || data.totals.prs_reviewed === 0 ? (
        <Card>
          <EmptyState
            icon={ChartColumn}
            title="No completed reviews in this range"
            description="Reviews show up here once they finish. Try a longer range, run a review, or load the sample data."
            action={
              <Button onClick={() => load.mutate()} disabled={load.isPending}>
                <Database className="size-4" aria-hidden /> Load sample data
              </Button>
            }
          />
        </Card>
      ) : (
        <div className={cn('space-y-5 transition-opacity duration-300', query.isPlaceholderData && 'opacity-60')}>
          <motion.div variants={listContainer} initial="hidden" animate="show" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <StatTile
              label="PRs reviewed"
              value={data.totals.prs_reviewed}
              icon={GitPullRequest}
              hint={`${plural(data.totals.files_reviewed, 'file')} reviewed`}
            />
            <StatTile
              label="Findings caught"
              value={data.totals.issues_found}
              icon={ScanSearch}
              hint={`${data.severity_counts.critical} critical · ${data.severity_counts.warning} warning · ${data.severity_counts.info} info`}
            />
            <StatTile
              label="False-positive rate"
              value={data.false_positive_rate === null ? null : data.false_positive_rate * 100}
              format={(value) => `${value.toFixed(value > 0 && value < 10 ? 1 : 0)}%`}
              icon={Flag}
              hint={
                data.false_positive_rate === null
                  ? 'Triage findings to measure precision'
                  : `${data.totals.false_positives} of ${data.totals.accepted + data.totals.dismissed + data.totals.false_positives} triaged findings`
              }
            />
            <StatTile
              label="Review time saved"
              value={data.minutes_saved}
              format={formatMinutes}
              icon={Timer}
              hint={`Estimate: ${data.minutes_per_file} min of manual first-pass review per file`}
            />
            <StatTile
              label="LLM spend"
              value={data.total_cost_usd}
              format={formatCost}
              icon={Coins}
              hint={`${formatCompact(data.total_tokens)} tokens${data.average_review_seconds ? ` · ${data.average_review_seconds}s avg review` : ''}`}
            />
          </motion.div>

          <motion.div variants={listContainer} initial="hidden" animate="show" className="grid items-stretch gap-5 lg:grid-cols-3">
            <motion.div variants={riseIn} className="lg:col-span-2">
              <ChartCard
                className="h-full"
                title="PR health over time"
                description={`Average ${data.average_health_score ?? '—'} across ${plural(data.score_trend.length, 'review')}`}
                table={
                  <DataTable
                    head={['Review', 'Date', 'Score']}
                    rows={data.score_trend.map((point) => [
                      <span key="label" className="font-mono text-xs">
                        {point.label}
                      </span>,
                      shortDate(point.date),
                      point.score,
                    ])}
                  />
                }
              >
                <ScoreTrendChart points={data.score_trend} />
              </ChartCard>
            </motion.div>

            <motion.div variants={riseIn}>
              <ChartCard
                className="h-full"
                title="Findings by category"
                description="All severities, most common first"
                table={
                  <DataTable
                    head={['Category', 'Total', 'Critical', 'Warning', 'Info']}
                    rows={data.categories.map((row) => [CATEGORY_META[row.category].label, row.total, row.critical, row.warning, row.info])}
                  />
                }
              >
                <CategoryBarChart categories={data.categories} />
              </ChartCard>
            </motion.div>

            <motion.div variants={riseIn} className="lg:col-span-2">
              <ChartCard
                className="h-full"
                title="Findings per week"
                description="Stacked by category"
                legend={<CategoryLegend />}
                table={
                  <DataTable
                    head={['Week', 'Reviews', ...CATEGORIES.map((category) => CATEGORY_META[category].label)]}
                    rows={toWeeks(data.weekly).map((week) => [week.label, week.reviews, ...CATEGORIES.map((category) => week[category])])}
                  />
                }
              >
                <WeeklyFindingsChart weekly={data.weekly} />
              </ChartCard>
            </motion.div>

            <motion.div variants={riseIn}>
              <Card className="h-full">
                <CardHeader title="Reviewer precision" description="Developer verdicts on findings, per category" />
                <div className="px-3 pb-5 pt-4">
                  <PrecisionBreakdown categories={data.categories} />
                </div>
              </Card>
            </motion.div>
          </motion.div>
        </div>
      )}
    </div>
  )
}

function AnalyticsSkeleton() {
  return (
    <div className="space-y-5" aria-busy="true">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        {Array.from({ length: 5 }, (_, index) => (
          <Card key={index} className="space-y-3 p-5">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="h-8 w-20" />
            <Skeleton className="h-3 w-32" />
          </Card>
        ))}
      </div>
      <div className="grid gap-5 lg:grid-cols-3">
        <Skeleton className="h-80 lg:col-span-2" />
        <Skeleton className="h-80" />
      </div>
    </div>
  )
}
