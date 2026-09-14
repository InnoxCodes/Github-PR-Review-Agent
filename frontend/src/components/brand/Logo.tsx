import { useId } from 'react'
import { cn } from '@/lib/cn'

export function LogoMark({ className }: { className?: string }) {
  const gradient = useId()
  return (
    <svg viewBox="0 0 32 32" fill="none" aria-hidden className={cn('size-8', className)}>
      <defs>
        <linearGradient id={gradient} x1="4" y1="2" x2="28" y2="30" gradientUnits="userSpaceOnUse">
          <stop stopColor="#4ADE80" />
          <stop offset="1" stopColor="#16A34A" />
        </linearGradient>
      </defs>
      <rect x="1" y="1" width="30" height="30" rx="8" fill="#0A0F1C" />
      <rect x="1.5" y="1.5" width="29" height="29" rx="7.5" stroke={`url(#${gradient})`} strokeOpacity=".55" />
      <path
        d="M12 10.5 6.5 16l5.5 5.5M20 10.5l5.5 5.5-5.5 5.5"
        stroke={`url(#${gradient})`}
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="m16 11.2 1.15 3.05 3.05 1.15-3.05 1.15L16 19.6l-1.15-3.05-3.05-1.15 3.05-1.15z" fill="#F8FAFC" />
    </svg>
  )
}

export function Logo({ compact = false, className }: { compact?: boolean; className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-2.5', className)}>
      <LogoMark />
      {!compact && (
        <span className="font-mono text-[15px] font-semibold tracking-tight text-fg">
          Review<span className="text-accent-text">Mind</span>
        </span>
      )}
    </span>
  )
}

export function GitHubMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden className={cn('size-4', className)}>
      <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
    </svg>
  )
}
