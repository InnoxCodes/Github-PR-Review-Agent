import { useQuery } from '@tanstack/react-query'
import { Command } from 'cmdk'
import { ChartColumn, Database, FolderGit2, GitPullRequest, History, Keyboard, Moon, ScanSearch, Search, Sun, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { useNavigate } from 'react-router'
import { Dialog } from '@/components/ui/Dialog'
import { Kbd } from '@/components/ui/Kbd'
import { api, queryKeys } from '@/lib/api'
import { useSampleData } from '@/lib/hooks'
import { useTheme } from '@/lib/theme'

interface CommandPaletteProps {
  open: boolean
  onClose: () => void
  onShowShortcuts: () => void
}

const GROUP =
  '[&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:pb-1.5 [&_[cmdk-group-heading]]:pt-3 [&_[cmdk-group-heading]]:font-mono [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-[0.14em] [&_[cmdk-group-heading]]:text-fg-subtle'

export function CommandPalette({ open, onClose, onShowShortcuts }: CommandPaletteProps) {
  const navigate = useNavigate()
  const { theme, toggleTheme } = useTheme()
  const { load } = useSampleData()
  const reviews = useQuery({
    queryKey: queryKeys.reviews({ limit: 8 }),
    queryFn: () => api.listReviews({ limit: 8 }),
    enabled: open,
  })

  const run = (action: () => void) => {
    onClose()
    action()
  }

  return (
    <Dialog open={open} onClose={onClose} title="Command menu" hideHeader placement="top" className="max-w-xl">
      <Command label="Command menu" loop>
        <div className="flex items-center gap-3 border-b border-line px-4">
          <Search className="size-4 shrink-0 text-fg-muted" aria-hidden />
          <Command.Input
            data-autofocus
            placeholder="Search reviews, pages and actions…"
            className="h-14 min-w-0 flex-1 bg-transparent text-[15px] text-fg placeholder:text-fg-subtle focus:outline-none focus-visible:outline-none"
          />
          <Kbd>esc</Kbd>
        </div>
        <Command.List className="max-h-[min(60vh,440px)] overflow-y-auto p-2 scrollbar-thin">
          <Command.Empty className="px-3 py-10 text-center text-sm text-fg-muted">No matches.</Command.Empty>

          <Command.Group heading="Go to" className={GROUP}>
            <Item icon={ScanSearch} shortcut="g h" onSelect={() => run(() => navigate('/'))}>
              New review
            </Item>
            <Item icon={History} shortcut="g r" onSelect={() => run(() => navigate('/reviews'))}>
              Reviews
            </Item>
            <Item icon={ChartColumn} shortcut="g a" onSelect={() => run(() => navigate('/analytics'))}>
              Analytics
            </Item>
            <Item icon={FolderGit2} shortcut="g p" onSelect={() => run(() => navigate('/repos'))}>
              Repositories
            </Item>
          </Command.Group>

          {reviews.data && reviews.data.length > 0 && (
            <Command.Group heading="Recent reviews" className={GROUP}>
              {reviews.data.map((review) => (
                <Item
                  key={review.id}
                  value={`${review.owner}/${review.repo}#${review.pr_number} ${review.pr_title ?? ''}`}
                  icon={GitPullRequest}
                  onSelect={() => run(() => navigate(`/reviews/${review.id}`))}
                  trailing={
                    <span className="font-mono text-xs text-fg-subtle">
                      {review.repo}#{review.pr_number}
                    </span>
                  }
                >
                  <span className="truncate">{review.pr_title ?? 'Pull request'}</span>
                </Item>
              ))}
            </Command.Group>
          )}

          <Command.Group heading="Actions" className={GROUP}>
            <Item icon={theme === 'dark' ? Sun : Moon} shortcut="t" onSelect={() => run(toggleTheme)}>
              Switch to {theme === 'dark' ? 'light' : 'dark'} theme
            </Item>
            <Item icon={Keyboard} shortcut="?" onSelect={() => run(onShowShortcuts)}>
              Keyboard shortcuts
            </Item>
            <Item icon={Database} onSelect={() => run(() => load.mutate())}>
              Load sample data
            </Item>
          </Command.Group>
        </Command.List>
      </Command>
    </Dialog>
  )
}

interface ItemProps {
  icon: LucideIcon
  children: ReactNode
  onSelect: () => void
  shortcut?: string
  value?: string
  trailing?: ReactNode
}

function Item({ icon: Icon, children, onSelect, shortcut, value, trailing }: ItemProps) {
  return (
    <Command.Item
      value={value}
      onSelect={onSelect}
      className="flex h-10 cursor-pointer items-center gap-3 rounded-lg px-2.5 text-sm text-fg-2 transition-colors data-[selected=true]:bg-muted data-[selected=true]:text-fg"
    >
      <Icon className="size-4 shrink-0 text-fg-muted" aria-hidden />
      <span className="flex min-w-0 flex-1 items-center gap-2">{children}</span>
      {trailing}
      {shortcut && (
        <span className="flex items-center gap-1">
          {shortcut.split(' ').map((key) => (
            <Kbd key={key}>{key}</Kbd>
          ))}
        </span>
      )}
    </Command.Item>
  )
}
