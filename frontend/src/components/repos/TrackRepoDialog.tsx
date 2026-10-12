import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Eye, EyeOff, LoaderCircle, Lock } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { api, queryKeys } from '@/lib/api'
import { cn } from '@/lib/cn'

const INPUT =
  'h-10 w-full rounded-lg border border-line-strong bg-sunken px-3 font-mono text-sm text-fg placeholder:text-fg-subtle transition-[border-color,box-shadow] duration-200 focus:border-accent/60 focus:shadow-glow focus-visible:outline-none'

export function TrackRepoDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient()
  const [repository, setRepository] = useState('')
  const [token, setToken] = useState('')
  const [reveal, setReveal] = useState(false)

  const mutation = useMutation({
    mutationFn: () => api.trackRepo(repository.trim(), token.trim() || undefined),
    onSuccess: (repo) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.repos })
      toast.success(`Tracking ${repo.full_name}`, {
        description: repo.has_token ? 'Access token encrypted and stored.' : undefined,
      })
      setRepository('')
      setToken('')
      onClose()
    },
  })

  function close() {
    mutation.reset()
    onClose()
  }

  return (
    <Dialog
      open={open}
      onClose={close}
      title="Track a repository"
      description="See health trends per repository, and review private pull requests with a stored token."
      footer={
        <>
          <Button variant="ghost" onClick={close}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" form="track-repo-form" disabled={!repository.trim() || mutation.isPending}>
            {mutation.isPending && <LoaderCircle className="spin-slow size-4" aria-hidden />}
            Track repository
          </Button>
        </>
      }
    >
      <form
        id="track-repo-form"
        className="space-y-5"
        onSubmit={(event) => {
          event.preventDefault()
          if (repository.trim()) mutation.mutate()
        }}
      >
        <div>
          <label htmlFor="repo-name" className="text-[13px] font-medium text-fg-2">
            Repository
          </label>
          <input
            id="repo-name"
            data-autofocus
            value={repository}
            onChange={(event) => setRepository(event.target.value)}
            placeholder="owner/name or https://github.com/owner/name"
            autoComplete="off"
            spellCheck={false}
            aria-invalid={mutation.isError}
            aria-describedby={mutation.isError ? 'repo-error' : undefined}
            className={cn(INPUT, 'mt-1.5', mutation.isError && 'border-critical/60')}
          />
          {mutation.error && (
            <p id="repo-error" role="alert" className="mt-1.5 text-[13px] text-critical-text">
              {mutation.error.message}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="repo-token" className="flex items-center justify-between text-[13px] font-medium text-fg-2">
            Access token <span className="font-normal text-fg-muted">Optional</span>
          </label>
          <div className="relative mt-1.5">
            <input
              id="repo-token"
              type={reveal ? 'text' : 'password'}
              value={token}
              onChange={(event) => setToken(event.target.value)}
              placeholder="github_pat_…"
              autoComplete="off"
              spellCheck={false}
              aria-describedby="repo-token-help"
              className={cn(INPUT, 'pr-11')}
            />
            <button
              type="button"
              onClick={() => setReveal((value) => !value)}
              aria-label={reveal ? 'Hide token' : 'Show token'}
              className="absolute right-1 top-1/2 grid size-8 -translate-y-1/2 place-items-center rounded-md text-fg-muted transition-colors hover:bg-muted hover:text-fg"
            >
              {reveal ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
          <p id="repo-token-help" className="mt-2 flex items-start gap-1.5 text-xs leading-relaxed text-fg-muted">
            <Lock className="mt-0.5 size-3.5 shrink-0" aria-hidden />
            Only needed for private repositories, a fine-grained token with read-only Pull requests and Contents access is enough.
            It's encrypted before it reaches the database and never sent back to the browser.
          </p>
        </div>
      </form>
    </Dialog>
  )
}
