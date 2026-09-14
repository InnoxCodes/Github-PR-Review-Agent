import { Dialog } from '@/components/ui/Dialog'
import { Kbd } from '@/components/ui/Kbd'

const GROUPS: { title: string; items: { keys: string[]; label: string }[] }[] = [
  {
    title: 'Everywhere',
    items: [
      { keys: ['⌘', 'K'], label: 'Command menu' },
      { keys: ['?'], label: 'Keyboard shortcuts' },
      { keys: ['t'], label: 'Toggle light / dark' },
      { keys: ['g', 'h'], label: 'New review' },
      { keys: ['g', 'r'], label: 'Reviews' },
      { keys: ['g', 'a'], label: 'Analytics' },
      { keys: ['g', 'p'], label: 'Repositories' },
      { keys: ['/'], label: 'Focus the PR input' },
    ],
  },
  {
    title: 'Reviewing findings',
    items: [
      { keys: ['j'], label: 'Next finding' },
      { keys: ['k'], label: 'Previous finding' },
      { keys: ['a'], label: 'Accept' },
      { keys: ['d'], label: 'Dismiss' },
      { keys: ['f'], label: 'Flag as false positive' },
      { keys: ['u'], label: 'Reopen' },
      { keys: ['c'], label: 'Copy suggested fix' },
      { keys: ['esc'], label: 'Clear selection' },
    ],
  },
]

export function ShortcutsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Dialog open={open} onClose={onClose} title="Keyboard shortcuts" description="Triage a whole review without touching the mouse." className="max-w-2xl">
      <div className="grid gap-6 sm:grid-cols-2">
        {GROUPS.map((group) => (
          <section key={group.title}>
            <h3 className="mb-2 font-mono text-xs uppercase tracking-[0.14em] text-fg-muted">{group.title}</h3>
            <ul className="divide-y divide-line">
              {group.items.map((item) => (
                <li key={item.label} className="flex items-center justify-between gap-4 py-2 text-sm text-fg-2">
                  {item.label}
                  <span className="flex items-center gap-1">
                    {item.keys.map((key, index) => (
                      <Kbd key={index}>{key}</Kbd>
                    ))}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </Dialog>
  )
}
