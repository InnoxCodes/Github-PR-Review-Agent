import { useEffect, useRef } from 'react'
import { usePrefersReducedMotion } from '@/lib/hooks'
import { useTheme } from '@/lib/theme'

interface Particle {
  x: number
  y: number
  vx: number
  vy: number
  r: number
  accent: boolean
}

const LINK_DISTANCE = 120

/** Drifting aurora + a faint constellation of nodes. Paused when the tab is hidden; static for reduced motion. */
export function AnimatedBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const reduceMotion = usePrefersReducedMotion()
  const { theme } = useTheme()

  useEffect(() => {
    const canvas = canvasRef.current
    const context = canvas?.getContext('2d')
    if (!canvas || !context) return

    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    const ink = theme === 'dark' ? '148,163,184' : '71,85,105'
    const accent = theme === 'dark' ? '74,222,128' : '22,163,74'
    let width = 0
    let height = 0
    let frame = 0

    const count = Math.round(Math.min(64, Math.max(24, window.innerWidth / 24)))
    const particles: Particle[] = Array.from({ length: count }, (_, index) => ({
      x: Math.random(),
      y: Math.random(),
      vx: (Math.random() - 0.5) * 0.00022,
      vy: (Math.random() - 0.5) * 0.00022,
      r: Math.random() * 1.3 + 0.7,
      accent: index % 8 === 0,
    }))

    const resize = () => {
      const rect = canvas.getBoundingClientRect()
      width = rect.width
      height = rect.height
      canvas.width = Math.round(width * dpr)
      canvas.height = Math.round(height * dpr)
      context.setTransform(dpr, 0, 0, dpr, 0, 0)
    }

    const draw = () => {
      context.clearRect(0, 0, width, height)
      for (const particle of particles) {
        if (!reduceMotion) {
          particle.x += particle.vx * 16
          particle.y += particle.vy * 16
          if (particle.x < 0 || particle.x > 1) particle.vx *= -1
          if (particle.y < 0 || particle.y > 1) particle.vy *= -1
        }
      }
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const a = particles[i]
          const b = particles[j]
          const distance = Math.hypot((a.x - b.x) * width, (a.y - b.y) * height)
          if (distance > LINK_DISTANCE) continue
          context.strokeStyle = `rgba(${ink},${(1 - distance / LINK_DISTANCE) * 0.14})`
          context.lineWidth = 1
          context.beginPath()
          context.moveTo(a.x * width, a.y * height)
          context.lineTo(b.x * width, b.y * height)
          context.stroke()
        }
      }
      for (const particle of particles) {
        context.fillStyle = particle.accent ? `rgba(${accent},0.75)` : `rgba(${ink},0.4)`
        context.beginPath()
        context.arc(particle.x * width, particle.y * height, particle.accent ? particle.r + 0.6 : particle.r, 0, Math.PI * 2)
        context.fill()
      }
      if (!reduceMotion && !document.hidden) frame = requestAnimationFrame(draw)
    }

    resize()
    draw()

    const observer = new ResizeObserver(() => {
      resize()
      if (reduceMotion) draw()
    })
    observer.observe(canvas)
    const onVisibility = () => {
      cancelAnimationFrame(frame)
      if (!document.hidden && !reduceMotion) frame = requestAnimationFrame(draw)
    }
    document.addEventListener('visibilitychange', onVisibility)

    return () => {
      cancelAnimationFrame(frame)
      observer.disconnect()
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [reduceMotion, theme])

  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
      <div className="aurora-blob -top-40 left-[10%] h-[420px] w-[520px] bg-accent/20" />
      <div className="aurora-blob -top-24 right-[8%] h-[380px] w-[460px] bg-sky-500/15 [animation-delay:-8s]" />
      <div className="aurora-blob top-[35%] left-[40%] h-[300px] w-[420px] bg-violet-500/10 [animation-delay:-15s]" />
      <div className="bg-grid absolute inset-0 opacity-70 [mask-image:radial-gradient(ellipse_70%_60%_at_50%_0%,black,transparent)]" />
      <canvas ref={canvasRef} className="absolute inset-0 size-full [mask-image:radial-gradient(ellipse_75%_65%_at_50%_30%,black,transparent)]" />
    </div>
  )
}
