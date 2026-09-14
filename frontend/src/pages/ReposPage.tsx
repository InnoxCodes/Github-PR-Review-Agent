import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { CloudOff, FolderGit2, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { PageHeader } from '@/components/layout/PageHeader'
import { RepoCard } from '@/components/repos/RepoCard'
import { TrackRepoDialog } from '@/components/repos/TrackRepoDialog'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Dialog } from '@/components/ui/Dialog'
import { EmptyState } from '@/components/ui/EmptyState'
import { Skeleton } from '@/components/ui/Skeleton'
import { api, queryKeys } from '@/lib/api'
import { listContainer } from '@/lib/motion'
import type { Repository } from '@/lib/types'

export default function ReposPage() {
  const queryClient = useQueryClient()
  const [trackOpen, setTrackOpen] = useState(false)
  const [removing, setRemoving] = useState<Repository | null>(null)
  const repos = useQuery({ queryKey: queryKeys.repos, queryFn: api.listRepos })

  const remove = useMutation({
    mutationFn: (repo: Repository) => api.deleteRepo(repo.id),
    onSuccess: (_, repo) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.repos })
      toast.success(`Stopped tracking ${repo.full_name}`)
      setRemoving(null)
    },
    onError: (error) => toast.error("Couldn't remove the repository", { description: error.message }),
  })

  return (
    <div className="mx-auto max-w-7xl space-y-6 px-5 py-8 sm:py-10">
      <PageHeader
        eyebrow="Workspace"
        title="Repositories"
        description="Health trends per repository. Repositories appear automatically after their first review — track one to store a token for private pull requests."
        actions={
          <Button variant="primary" onClick={() => setTrackOpen(true)}>
            <Plus className="size-4" aria-hidden /> Track repository
          </Button>
        }
      />

      {repos.isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3" aria-busy="true">
          {Array.from({ length: 3 }, (_, index) => (
            <Card key={index} className="space-y-4 p-5">
              <div className="flex items-center gap-3">
                <Skeleton className="size-10 rounded-xl" />
                <Skeleton className="h-4 w-40" />
              </div>
              <Skeleton className="h-10" />
              <Skeleton className="h-20" />
              <Skeleton className="h-9" />
            </Card>
          ))}
        </div>
      ) : repos.isError ? (
        <Card>
          <EmptyState icon={CloudOff} title="Can't reach the API" description={repos.error.message} />
        </Card>
      ) : !repos.data || repos.data.length === 0 ? (
        <Card>
          <EmptyState
            icon={FolderGit2}
            title="No repositories yet"
            description="Repositories are added automatically after their first review. Track one now to store an access token for private pull requests."
            action={
              <Button variant="primary" onClick={() => setTrackOpen(true)}>
                <Plus className="size-4" aria-hidden /> Track repository
              </Button>
            }
          />
        </Card>
      ) : (
        <motion.ul variants={listContainer} initial="hidden" animate="show" className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {repos.data.map((repo) => (
            <RepoCard key={repo.id} repo={repo} onRemove={() => setRemoving(repo)} />
          ))}
        </motion.ul>
      )}

      <TrackRepoDialog open={trackOpen} onClose={() => setTrackOpen(false)} />

      <Dialog
        open={removing !== null}
        onClose={() => setRemoving(null)}
        title={`Stop tracking ${removing?.full_name ?? 'repository'}?`}
        description="Its stored access token is deleted. Past reviews stay in your history."
        footer={
          <>
            <Button variant="ghost" onClick={() => setRemoving(null)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={() => removing && remove.mutate(removing)} disabled={remove.isPending}>
              <Trash2 className="size-4" aria-hidden /> Stop tracking
            </Button>
          </>
        }
      >
        <p className="text-sm text-fg-muted">You can track it again at any time.</p>
      </Dialog>
    </div>
  )
}
