import { SearchX } from 'lucide-react'
import { Link } from 'react-router'
import { buttonClasses } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'

export default function NotFoundPage() {
  return (
    <div className="mx-auto max-w-2xl px-5 py-20">
      <Card>
        <EmptyState
          icon={SearchX}
          title="Page not found"
          description="That page doesn't exist. It may have moved, or the link is mistyped."
          action={
            <Link to="/" className={buttonClasses('primary', 'sm')}>
              Back to ReviewMind
            </Link>
          }
        />
      </Card>
    </div>
  )
}
