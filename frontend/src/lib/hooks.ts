import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { api } from './api'

export function useSampleData() {
  const queryClient = useQueryClient()

  const load = useMutation({
    mutationFn: api.loadSampleData,
    onSuccess: (result) => {
      queryClient.invalidateQueries()
      toast.success('Sample data loaded', {
        description: `${result.reviews} hand-written sample reviews across ${result.repositories} fictional repositories.`,
      })
    },
    onError: (error) => toast.error('Could not load sample data', { description: error.message }),
  })

  const clear = useMutation({
    mutationFn: api.clearSampleData,
    onSuccess: () => {
      queryClient.invalidateQueries()
      toast.success('Sample data removed')
    },
    onError: (error) => toast.error('Could not remove sample data', { description: error.message }),
  })

  return { load, clear }
}

export function useElapsedSeconds(startIso: string | null | undefined, running: boolean): number {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (!running) return
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [running])

  if (!startIso) return 0
  return Math.max(0, Math.round((now - new Date(startIso).getTime()) / 1000))
}

export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)')
    const onChange = () => setReduced(query.matches)
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])
  return reduced
}
