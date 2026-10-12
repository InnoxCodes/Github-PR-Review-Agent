import { useEffect, useReducer, useRef } from 'react'
import { DEMO, reviewStreamUrl } from './api'
import type { FileState, Issue, ReviewFile, ReviewStatus, ReviewSummary, StreamEvent } from './types'

export interface StreamFile extends ReviewFile {
  chunks: number
  retries: number
}

export interface StreamState {
  connection: 'connecting' | 'open' | 'closed' | 'error'
  status: ReviewStatus | null
  message: string | null
  model: string | null
  review: ReviewSummary | null
  files: StreamFile[]
  issues: Issue[]
  filesDone: number
  filesTotal: number
  costUsd: number | null
  tokens: number
  retries: { filename: string; attempt: number; reason: string }[]
  terminal: 'completed' | 'failed' | null
  error: string | null
  lastEventId: number
}

const initialState: StreamState = {
  connection: 'connecting',
  status: null,
  message: null,
  model: null,
  review: null,
  files: [],
  issues: [],
  filesDone: 0,
  filesTotal: 0,
  costUsd: null,
  tokens: 0,
  retries: [],
  terminal: null,
  error: null,
  lastEventId: 0,
}

type Action =
  | { kind: 'reset' }
  | { kind: 'connection'; connection: StreamState['connection'] }
  | { kind: 'event'; id: number; event: StreamEvent }

function patchFile(files: StreamFile[], fileId: number | null, patch: Partial<StreamFile>): StreamFile[] {
  return files.map((file) => (file.id === fileId ? { ...file, ...patch } : file))
}

function reducer(state: StreamState, action: Action): StreamState {
  if (action.kind === 'reset') return initialState
  if (action.kind === 'connection') return { ...state, connection: action.connection }
  if (action.id && action.id <= state.lastEventId) return state

  const next = { ...state, lastEventId: action.id || state.lastEventId }
  const { event } = action
  switch (event.type) {
    case 'status':
      return { ...next, status: event.data.status, message: event.data.message, model: event.data.model ?? next.model }
    case 'pr': {
      const reviewable = event.data.files.filter((file) => file.state !== 'skipped').length
      return {
        ...next,
        review: event.data.review,
        files: event.data.files.map((file) => ({ ...file, chunks: file.chunk_count, retries: 0 })),
        filesTotal: reviewable,
      }
    }
    case 'file.started':
      return {
        ...next,
        files: patchFile(next.files, event.data.file_id, { state: 'reviewing', chunks: event.data.chunks }),
      }
    case 'issues':
      return {
        ...next,
        issues: [...event.data.issues, ...next.issues],
        files: next.files.map((file) =>
          file.id === event.data.file_id ? { ...file, issue_count: file.issue_count + event.data.issues.length } : file,
        ),
      }
    case 'file.retry':
      return {
        ...next,
        retries: [...next.retries, event.data],
        files: next.files.map((file) => (file.id === event.data.file_id ? { ...file, retries: file.retries + 1 } : file)),
      }
    case 'file.completed':
      return {
        ...next,
        files: patchFile(next.files, event.data.file_id, {
          state: event.data.state as FileState,
          summary: event.data.summary,
          error: event.data.error,
          issue_count: event.data.issue_count,
        }),
        filesDone: event.data.files_done,
        filesTotal: event.data.files_total,
        costUsd: event.data.cost_usd,
        tokens: event.data.tokens,
      }
    case 'review.completed':
      return { ...next, status: 'completed', review: event.data.review, terminal: 'completed', message: null }
    case 'review.failed':
      return {
        ...next,
        status: 'failed',
        review: event.data.review ?? next.review,
        terminal: 'failed',
        error: event.data.error,
        message: null,
      }
  }
}

const EVENT_TYPES: StreamEvent['type'][] = [
  'status',
  'pr',
  'file.started',
  'issues',
  'file.retry',
  'file.completed',
  'review.completed',
  'review.failed',
]

interface Options {
  enabled: boolean
  replay?: boolean
  onTerminal?: (outcome: 'completed' | 'failed', state: StreamState) => void
}

/** Subscribes to a review's SSE stream. EventSource reconnects with Last-Event-ID on its own. */
export function useReviewStream(reviewId: string | undefined, { enabled, replay = false, onTerminal }: Options) {
  const [state, dispatch] = useReducer(reducer, initialState)
  const stateRef = useRef(state)
  const onTerminalRef = useRef(onTerminal)

  useEffect(() => {
    stateRef.current = state
    onTerminalRef.current = onTerminal
  })

  useEffect(() => {
    if (!enabled || !reviewId) return
    dispatch({ kind: 'reset' })

    if (DEMO) {
      // No server in the hosted demo: replay the stored events at a watchable pace.
      let cancelled = false
      const pause = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))
      const delays: Record<string, number> = { status: 400, pr: 700, 'file.started': 350, 'file.retry': 600, issues: 600, 'file.completed': 400 }
      ;(async () => {
        const { demoEvents } = await import('@/demo/demo')
        dispatch({ kind: 'connection', connection: 'open' })
        for (const stored of demoEvents(reviewId)) {
          await pause(delays[stored.type] ?? 600)
          if (cancelled) return
          const event = { type: stored.type, data: stored.data } as StreamEvent
          dispatch({ kind: 'event', id: stored.id, event })
          if (event.type === 'review.completed' || event.type === 'review.failed') {
            dispatch({ kind: 'connection', connection: 'closed' })
            const outcome = event.type === 'review.completed' ? 'completed' : 'failed'
            queueMicrotask(() => onTerminalRef.current?.(outcome, stateRef.current))
          }
        }
      })()
      return () => {
        cancelled = true
      }
    }

    const source = new EventSource(reviewStreamUrl(reviewId, replay))
    let finished = false

    source.onopen = () => dispatch({ kind: 'connection', connection: 'open' })
    source.onerror = () => {
      if (finished) return
      dispatch({ kind: 'connection', connection: source.readyState === EventSource.CLOSED ? 'error' : 'connecting' })
    }

    const handlers = EVENT_TYPES.map((type) => {
      const handler = (message: MessageEvent<string>) => {
        const event = { type, data: JSON.parse(message.data) } as StreamEvent
        dispatch({ kind: 'event', id: Number(message.lastEventId) || 0, event })
        if (type === 'review.completed' || type === 'review.failed') {
          finished = true
          source.close()
          dispatch({ kind: 'connection', connection: 'closed' })
          const outcome = type === 'review.completed' ? 'completed' : 'failed'
          // Let the reducer apply the terminal event before callers read the final state.
          queueMicrotask(() => onTerminalRef.current?.(outcome, stateRef.current))
        }
      }
      source.addEventListener(type, handler as EventListener)
      return [type, handler] as const
    })

    const onEnd = () => {
      finished = true
      source.close()
      dispatch({ kind: 'connection', connection: 'closed' })
    }
    source.addEventListener('stream.end', onEnd)

    return () => {
      finished = true
      for (const [type, handler] of handlers) source.removeEventListener(type, handler as EventListener)
      source.removeEventListener('stream.end', onEnd)
      source.close()
    }
  }, [reviewId, enabled, replay])

  return state
}
