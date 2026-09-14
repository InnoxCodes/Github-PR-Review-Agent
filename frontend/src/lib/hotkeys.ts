import { useEffect, useRef } from 'react'

export type HotkeyMap = Record<string, (event: KeyboardEvent) => void>

const SEQUENCE_TIMEOUT_MS = 900

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  return target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)
}

/**
 * Single keys ("j", "?", "Escape") and two-key sequences ("g a"). Ignored while typing in a
 * field or when a modifier is held, so they never fight the browser or text entry.
 */
export function useHotkeys(bindings: HotkeyMap, enabled = true): void {
  const bindingsRef = useRef(bindings)

  useEffect(() => {
    bindingsRef.current = bindings
  })

  useEffect(() => {
    if (!enabled) return
    let pending: string | null = null
    let timer: ReturnType<typeof setTimeout> | undefined

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) return
      if (document.body.dataset.modalOpen) return
      if (isTypingTarget(event.target) && event.key !== 'Escape') return

      const key = event.key.length === 1 ? event.key.toLowerCase() : event.key
      const map = bindingsRef.current
      const combo = pending ? `${pending} ${key}` : key

      if (map[combo]) {
        event.preventDefault()
        pending = null
        map[combo](event)
        return
      }
      if (!pending && Object.keys(map).some((binding) => binding.startsWith(`${key} `))) {
        pending = key
        clearTimeout(timer)
        timer = setTimeout(() => {
          pending = null
        }, SEQUENCE_TIMEOUT_MS)
        return
      }
      pending = null
    }

    window.addEventListener('keydown', onKeyDown)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      clearTimeout(timer)
    }
  }, [enabled])
}
