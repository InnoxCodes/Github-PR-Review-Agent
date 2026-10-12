import { useMutation, useQueryClient } from '@tanstack/react-query'
import { GitPullRequest, LoaderCircle, ScanSearch } from 'lucide-react'
import { useRef, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'
import { Button } from '@/components/ui/Button'
import { Kbd } from '@/components/ui/Kbd'
import { api, ApiError, isPullRequestReference, queryKeys } from '@/lib/api'
import { cn } from '@/lib/cn'
import { useHotkeys } from '@/lib/hotkeys'

const EXAMPLES = ['sindresorhus/ky#880', 'encode/httpx#3690', 'fastapi/typer#1942']

interface PRInputProps {
  initialValue?: string
  llmReady: boolean | undefined
  onNeedsSetup: () => void
}

export function PRInput({ initialValue = '', llmReady, onNeedsSetup }: PRInputProps) {
  const [value, setValue] = useState(initialValue)
  const [touched, setTouched] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  useHotkeys({ '/': () => inputRef.current?.focus() })

  const mutation = useMutation({
    mutationFn: (reference: string) => api.createReview(reference),
    onSuccess: (review) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.allReviews })
      toast.success('Review started', { description: `${review.owner}/${review.repo}#${review.pr_number}` })
      navigate(`/reviews/${review.id}`)
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 503) {
        onNeedsSetup()
        return
      }
      toast.error("Couldn't start the review", { description: error.message })
    },
  })

  const valid = isPullRequestReference(value)
  const showError = touched && value.trim() !== '' && !valid

  function submit(event: FormEvent) {
    event.preventDefault()
    setTouched(true)
    if (!valid) {
      inputRef.current?.focus()
      return
    }
    if (llmReady === false) {
      onNeedsSetup()
      return
    }
    mutation.mutate(value.trim())
  }

  return (
    <form onSubmit={submit} noValidate className="w-full">
      <label htmlFor="pr-url" className="sr-only">
        GitHub pull request URL
      </label>
      <div
        className={cn(
          'group relative flex items-center gap-2 rounded-2xl border bg-surface/85 p-2 pl-4 shadow-pop backdrop-blur-xl',
          'transition-[border-color,box-shadow] duration-300 focus-within:shadow-glow',
          showError ? 'border-critical/60' : 'border-line-strong focus-within:border-accent/60',
        )}
      >
        <GitPullRequest className="size-5 shrink-0 text-fg-muted transition-colors group-focus-within:text-accent-text" aria-hidden />
        <input
          id="pr-url"
          ref={inputRef}
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onBlur={() => setTouched(true)}
          placeholder="https://github.com/owner/repo/pull/123"
          autoComplete="off"
          spellCheck={false}
          aria-invalid={showError}
          aria-describedby="pr-url-help"
          className="h-11 min-w-0 flex-1 bg-transparent font-mono text-[15px] text-fg placeholder:text-fg-subtle focus:outline-none focus-visible:outline-none"
        />
        <Kbd className="hidden sm:inline-flex">/</Kbd>
        <Button type="submit" variant="primary" size="lg" disabled={mutation.isPending} className="px-4 sm:px-5">
          {mutation.isPending ? <LoaderCircle className="spin-slow size-4" aria-hidden /> : <ScanSearch className="size-4" aria-hidden />}
          <span className="hidden sm:inline">{mutation.isPending ? 'Starting…' : 'Review PR'}</span>
        </Button>
      </div>
      <p
        id="pr-url-help"
        aria-live="polite"
        className={cn('mt-2.5 min-h-5 text-[13px]', showError ? 'text-critical-text' : 'text-fg-muted')}
      >
        {showError
          ? "That doesn't look like a pull request, try https://github.com/owner/repo/pull/123 or owner/repo#123."
          : 'Any public pull request works. Private repositories need a tracked repo with a token.'}
      </p>
      <div className="mt-3 flex flex-wrap items-center justify-center gap-2">
        <span className="text-xs text-fg-subtle">Try</span>
        {EXAMPLES.map((example) => (
          <button
            key={example}
            type="button"
            onClick={() => {
              setValue(example)
              setTouched(false)
              inputRef.current?.focus()
            }}
            className="rounded-full border border-line bg-surface/60 px-3 py-1 font-mono text-xs text-fg-muted backdrop-blur transition-colors hover:border-line-strong hover:text-fg"
          >
            {example}
          </button>
        ))}
      </div>
    </form>
  )
}
