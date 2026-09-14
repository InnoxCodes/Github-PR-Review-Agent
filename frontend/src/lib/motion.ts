import type { Transition, Variants } from 'framer-motion'

// One shared motion vocabulary (ui-ux-pro-max: motion-consistency, spring-physics, exit-faster-than-enter).
export const spring: Transition = { type: 'spring', stiffness: 420, damping: 34, mass: 0.8 }
export const gentleSpring: Transition = { type: 'spring', stiffness: 240, damping: 28 }
export const easeOut: Transition = { duration: 0.32, ease: [0.22, 1, 0.36, 1] }
export const exitFast: Transition = { duration: 0.18, ease: [0.4, 0, 1, 1] }

// 45ms between items: inside the 30–50ms stagger band — reads as a wave, not a wait.
export const STAGGER = 0.045

export const listContainer: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: STAGGER } },
}

export const riseIn: Variants = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: easeOut },
  exit: { opacity: 0, y: -6, transition: exitFast },
}

export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: easeOut },
  exit: { opacity: 0, transition: exitFast },
}
