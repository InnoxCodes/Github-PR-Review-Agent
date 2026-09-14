import { useState } from 'react'
import { cn } from '@/lib/cn'

interface AvatarProps {
  name: string
  src?: string | null
  size?: number
  className?: string
}

export function Avatar({ name, src, size = 24, className }: AvatarProps) {
  const [failed, setFailed] = useState(false)

  if (src && !failed) {
    return (
      <img
        src={src}
        alt=""
        width={size}
        height={size}
        loading="lazy"
        onError={() => setFailed(true)}
        className={cn('shrink-0 rounded-full ring-1 ring-line-strong', className)}
      />
    )
  }

  const hue = [...name].reduce((hash, char) => (hash * 31 + char.charCodeAt(0)) % 360, 17)
  return (
    <span
      aria-hidden
      className={cn('grid shrink-0 place-items-center rounded-full font-mono font-semibold uppercase text-white', className)}
      style={{
        width: size,
        height: size,
        fontSize: Math.max(10, size * 0.4),
        background: `linear-gradient(135deg, oklch(0.64 0.14 ${hue}), oklch(0.5 0.14 ${(hue + 50) % 360}))`,
      }}
    >
      {name.replace(/[^a-z0-9]/gi, '').slice(0, 2)}
    </span>
  )
}
