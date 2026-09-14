import { useQuery } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import { ChartColumn, Command, FolderGit2, History, Keyboard, Menu, Moon, ScanSearch, Sun, X, type LucideIcon } from 'lucide-react'
import { Suspense, useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router'
import { Logo } from '@/components/brand/Logo'
import { Button } from '@/components/ui/Button'
import { Kbd } from '@/components/ui/Kbd'
import { Skeleton } from '@/components/ui/Skeleton'
import { api, queryKeys } from '@/lib/api'
import { cn } from '@/lib/cn'
import { useHotkeys } from '@/lib/hotkeys'
import { spring } from '@/lib/motion'
import { useTheme } from '@/lib/theme'
import { CommandPalette } from './CommandPalette'
import { ShortcutsDialog } from './ShortcutsDialog'

const NAV: { to: string; label: string; icon: LucideIcon; end?: boolean }[] = [
  { to: '/', label: 'New review', icon: ScanSearch, end: true },
  { to: '/reviews', label: 'Reviews', icon: History },
  { to: '/analytics', label: 'Analytics', icon: ChartColumn },
  { to: '/repos', label: 'Repositories', icon: FolderGit2 },
]

export function AppShell() {
  const navigate = useNavigate()
  const location = useLocation()
  const { theme, toggleTheme } = useTheme()
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [shortcutsOpen, setShortcutsOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [menuPath, setMenuPath] = useState(location.pathname)

  if (menuPath !== location.pathname) {
    setMenuPath(location.pathname)
    setMenuOpen(false)
  }

  useHotkeys({
    'g h': () => navigate('/'),
    'g r': () => navigate('/reviews'),
    'g a': () => navigate('/analytics'),
    'g p': () => navigate('/repos'),
    '?': () => setShortcutsOpen(true),
    t: toggleTheme,
  })

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setPaletteOpen((open) => !open)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  const sidebar = (
    <Sidebar
      onOpenPalette={() => setPaletteOpen(true)}
      onOpenShortcuts={() => setShortcutsOpen(true)}
      theme={theme}
      onToggleTheme={toggleTheme}
    />
  )

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[252px_minmax(0,1fr)]">
      <a
        href="#main"
        className="sr-only z-50 rounded-lg bg-accent px-3 py-2 text-accent-fg focus:not-sr-only focus:fixed focus:left-3 focus:top-3"
      >
        Skip to content
      </a>

      <aside className="sticky top-0 hidden h-dvh border-r border-line bg-page/80 backdrop-blur-xl lg:block">{sidebar}</aside>

      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-line bg-page/85 px-4 backdrop-blur-xl lg:hidden">
        <Logo />
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" onClick={() => setPaletteOpen(true)} aria-label="Open command menu">
            <Command className="size-4" />
          </Button>
          <Button variant="ghost" size="icon" onClick={() => setMenuOpen(true)} aria-label="Open navigation" aria-expanded={menuOpen}>
            <Menu className="size-5" />
          </Button>
        </div>
      </header>

      <AnimatePresence>
        {menuOpen && (
          <div className="fixed inset-0 z-40 lg:hidden">
            <motion.div
              className="absolute inset-0 bg-[rgb(3_6_14/0.6)] backdrop-blur-sm"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setMenuOpen(false)}
            />
            <motion.aside
              className="absolute inset-y-0 left-0 w-[272px] border-r border-line bg-page"
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={spring}
            >
              <Button variant="ghost" size="icon" className="absolute right-3 top-3" onClick={() => setMenuOpen(false)} aria-label="Close navigation">
                <X className="size-4" />
              </Button>
              {sidebar}
            </motion.aside>
          </div>
        )}
      </AnimatePresence>

      <main id="main" className="min-w-0">
        <Suspense fallback={<PageFallback />}>
          <Outlet />
        </Suspense>
      </main>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} onShowShortcuts={() => setShortcutsOpen(true)} />
      <ShortcutsDialog open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
    </div>
  )
}

interface SidebarProps {
  onOpenPalette: () => void
  onOpenShortcuts: () => void
  theme: 'dark' | 'light'
  onToggleTheme: () => void
}

function Sidebar({ onOpenPalette, onOpenShortcuts, theme, onToggleTheme }: SidebarProps) {
  const health = useQuery({ queryKey: queryKeys.health, queryFn: api.health, refetchInterval: 30_000 })
  const configured = health.data?.llm.configured

  return (
    <div className="flex h-full flex-col gap-6 p-4">
      <NavLink to="/" className="rounded-lg px-1.5 py-1" aria-label="ReviewMind home">
        <Logo />
      </NavLink>

      <button
        type="button"
        onClick={onOpenPalette}
        className="flex h-9 items-center gap-2 rounded-lg border border-line bg-surface/70 px-2.5 text-[13px] text-fg-muted transition-colors hover:border-line-strong hover:text-fg"
      >
        <Command className="size-3.5" aria-hidden />
        <span className="flex-1 text-left">Search…</span>
        <Kbd>⌘K</Kbd>
      </button>

      <nav aria-label="Main">
        <ul className="space-y-1">
          {NAV.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    'relative flex h-10 items-center gap-3 rounded-lg px-3 text-sm font-medium transition-colors duration-200',
                    isActive ? 'text-fg' : 'text-fg-muted hover:bg-muted/60 hover:text-fg',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive && (
                      <motion.span
                        layoutId="nav-active"
                        transition={spring}
                        className="absolute inset-0 -z-10 rounded-lg border border-line-strong bg-surface shadow-card"
                      />
                    )}
                    <item.icon className={cn('size-4', isActive && 'text-accent-text')} aria-hidden />
                    {item.label}
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <div className="mt-auto space-y-3">
        <div className="rounded-xl border border-line bg-surface/60 p-3">
          {health.isLoading ? (
            <Skeleton className="h-9" />
          ) : (
            <>
              <p className="flex items-center gap-2 text-xs font-medium text-fg-2">
                <span className={cn('size-2 rounded-full', configured ? 'bg-good' : 'bg-warning')} aria-hidden />
                {health.isError ? 'API unreachable' : configured ? 'LLM connected' : 'LLM not configured'}
              </p>
              <p className="mt-1 truncate font-mono text-xs text-fg-muted">
                {health.isError ? 'Start the backend on :8000' : (health.data?.llm.model ?? 'Sample data mode')}
              </p>
            </>
          )}
        </div>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="sm" className="flex-1 justify-start" onClick={onToggleTheme} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}>
            {theme === 'dark' ? <Sun className="size-4" aria-hidden /> : <Moon className="size-4" aria-hidden />}
            {theme === 'dark' ? 'Light mode' : 'Dark mode'}
          </Button>
          <Button variant="ghost" size="icon-sm" onClick={onOpenShortcuts} aria-label="Keyboard shortcuts">
            <Keyboard className="size-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}

function PageFallback() {
  return (
    <div className="mx-auto max-w-5xl space-y-4 px-6 py-10" aria-busy="true">
      <Skeleton className="h-8 w-64" />
      <Skeleton className="h-4 w-96" />
      <Skeleton className="h-64 w-full" />
    </div>
  )
}
