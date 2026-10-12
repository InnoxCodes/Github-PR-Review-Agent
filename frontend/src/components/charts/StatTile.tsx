import { motion } from 'framer-motion'
import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { AnimatedNumber } from '@/components/ui/AnimatedNumber'
import { Card } from '@/components/ui/Card'
import { riseIn } from '@/lib/motion'

interface StatTileProps {
  label: string
  value: number | null
  format?: (value: number) => string
  icon: LucideIcon
  hint?: ReactNode
}

export function StatTile({ label, value, format, icon: Icon, hint }: StatTileProps) {
  return (
    <motion.div variants={riseIn} className="h-full">
      <Card className="h-full p-5">
        <div className="flex items-center justify-between gap-3">
          <span className="text-[13px] font-medium text-fg-muted">{label}</span>
          <span className="grid size-8 place-items-center rounded-lg border border-line bg-raised text-fg-muted">
            <Icon className="size-4" aria-hidden />
          </span>
        </div>
        <p className="mt-3 text-[30px] font-semibold leading-none tracking-tight text-fg">
          {value === null ? <span className="text-fg-subtle">-</span> : <AnimatedNumber value={value} format={format} />}
        </p>
        {hint && <p className="mt-2 text-xs leading-relaxed text-fg-muted">{hint}</p>}
      </Card>
    </motion.div>
  )
}
