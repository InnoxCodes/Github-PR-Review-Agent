import { Toaster } from 'sonner'
import { useTheme } from '@/lib/theme'

export function AppToaster() {
  const { theme } = useTheme()
  return (
    <Toaster
      theme={theme}
      position="bottom-right"
      closeButton
      toastOptions={{
        duration: 4000,
        style: {
          background: 'var(--rm-raised)',
          color: 'var(--rm-fg)',
          border: '1px solid var(--rm-line-strong)',
          boxShadow: 'var(--rm-shadow-pop)',
          fontFamily: '"IBM Plex Sans", ui-sans-serif, system-ui, sans-serif',
        },
      }}
    />
  )
}
