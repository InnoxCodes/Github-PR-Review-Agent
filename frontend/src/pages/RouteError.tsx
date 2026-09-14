import { CloudOff } from 'lucide-react'
import { isRouteErrorResponse, useRouteError } from 'react-router'
import { buttonClasses } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'

export function RouteError() {
  const error = useRouteError()
  const message = isRouteErrorResponse(error)
    ? `${error.status} ${error.statusText}`
    : error instanceof Error
      ? error.message
      : 'Something unexpected happened.'

  return (
    <div className="grid min-h-dvh place-items-center bg-page p-6">
      <EmptyState
        icon={CloudOff}
        title="Something went wrong"
        description={message}
        action={
          <a href="/" className={buttonClasses('secondary', 'sm')}>
            Reload ReviewMind
          </a>
        }
      />
    </div>
  )
}
