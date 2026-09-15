import { motion } from 'framer-motion'
import { ArrowUpRight, FolderGit2, History, KeyRound, Lock, ScanSearch, Star, Trash2 } from 'lucide-react'
import { Link } from 'react-router'
import { Sparkline } from '@/components/charts/Sparkline'
import { Badge } from '@/components/ui/Badge'
import { Button, buttonClasses } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { cn } from '@/lib/cn'
import { formatCompact, relativeTime } from '@/lib/format'
import { GRADE_META, gradeFor } from '@/lib/meta'
import { riseIn } from '@/lib/motion'
import type { Repository } from '@/lib/types'

const DEMO_OWNER = 'reviewmind-demo'

export function RepoCard({ repo, onRemove }: { repo: Repository; onRemove: () => void }) {
  const isSample = repo.owner === DEMO_OWNER
  const grade = gradeFor(repo.average_health_score)
  const gradeMeta = grade ? GRADE_META[grade] : null
  const GradeIcon = gradeMeta?.icon

  return (
    <motion.li variants={riseIn} className="h-full">
      <Card className="flex h-full flex-col p-5 transition-[border-color,box-shadow,transform] duration-200 hover:-translate-y-0.5 hover:border-line-strong hover:shadow-pop">
        <div className="flex items-start gap-3">
          <span className="grid size-10 shrink-0 place-items-center rounded-xl border border-line bg-raised text-fg-muted">
            <FolderGit2 className="size-5" aria-hidden />
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate font-mono text-xs text-fg-muted">{repo.owner}</p>
            <h2 className="truncate font-mono text-[15px] font-semibold text-fg">{repo.name}</h2>
            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-fg-muted">
              {repo.language && <span>{repo.language}</span>}
              <span className="inline-flex items-center gap-1">
                <Star className="size-3.5" aria-hidden /> {formatCompact(repo.stars)}
              </span>
              {repo.is_private && (
                <span className="inline-flex items-center gap-1">
                  <Lock className="size-3.5" aria-hidden /> Private
                </span>
              )}
              {repo.has_token && (
                <span className="inline-flex items-center gap-1" title="Encrypted at rest; never returned by the API">
                  <KeyRound className="size-3.5" aria-hidden /> Token …{repo.token_hint ?? '••••'}
                </span>
              )}
            </div>
          </div>
          {isSample && <Badge tone="outline">Sample</Badge>}
        </div>

        <p className="mt-3 line-clamp-2 min-h-10 text-sm leading-relaxed text-fg-muted">{repo.description ?? 'No description.'}</p>

        <dl className="mt-4 grid grid-cols-3 gap-3 rounded-xl border border-line bg-sunken p-3">
          <div>
            <dt className="text-xs text-fg-muted">Avg health</dt>
            <dd className="mt-1 text-lg font-semibold text-fg">{repo.average_health_score ?? '—'}</dd>
            {gradeMeta && GradeIcon && (
              <dd className={cn('mt-0.5 inline-flex items-center gap-1 text-xs font-medium', gradeMeta.text)}>
                <GradeIcon className="size-3" aria-hidden /> {gradeMeta.label}
              </dd>
            )}
          </div>
          <div>
            <dt className="text-xs text-fg-muted">Reviews</dt>
            <dd className="mt-1 text-lg font-semibold text-fg">{repo.review_count}</dd>
          </div>
          <div>
            <dt className="text-xs text-fg-muted">Open findings</dt>
            <dd className="mt-1 text-lg font-semibold text-fg">{repo.open_issues}</dd>
          </div>
        </dl>

        <div className="mt-4 grid grid-cols-2 gap-3">
          <div>
            <p className="mb-1 text-xs text-fg-muted">Health, last {repo.score_history.length}</p>
            <Sparkline values={repo.score_history} domain={[0, 100]} label={`Health scores: ${repo.score_history.join(', ')}`} />
          </div>
          <div>
            <p className="mb-1 text-xs text-fg-muted">Findings per review</p>
            <Sparkline values={repo.issue_history} label={`Findings per review: ${repo.issue_history.join(', ')}`} />
          </div>
        </div>

        <div className="mt-auto flex items-center gap-2 border-t border-line pt-4 text-xs">
          <span className="mr-auto text-fg-muted">
            {repo.last_reviewed_at ? `Reviewed ${relativeTime(repo.last_reviewed_at)}` : 'Not reviewed yet'}
          </span>
          <Link to={`/reviews?repository=${encodeURIComponent(repo.full_name)}`} className={buttonClasses('ghost', 'sm')}>
            <History className="size-3.5" aria-hidden /> Reviews
          </Link>
          {isSample ? (
            <Link to="/" className={buttonClasses('outline', 'sm')}>
              <ScanSearch className="size-3.5" aria-hidden /> Review
            </Link>
          ) : (
            <a href={repo.html_url} target="_blank" rel="noreferrer" className={buttonClasses('outline', 'sm')}>
              GitHub <ArrowUpRight className="size-3.5" aria-hidden />
            </a>
          )}
          <Button variant="ghost" size="icon-sm" onClick={onRemove} aria-label={`Stop tracking ${repo.full_name}`}>
            <Trash2 className="size-4" />
          </Button>
        </div>
      </Card>
    </motion.li>
  )
}
