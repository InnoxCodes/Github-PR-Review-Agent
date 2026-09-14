import { ChartColumn, Table2 } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Card, CardHeader } from '@/components/ui/Card'
import { SegmentedControl } from '@/components/ui/SegmentedControl'
import { cn } from '@/lib/cn'

interface ChartCardProps {
  title: string
  description?: ReactNode
  legend?: ReactNode
  children: ReactNode
  table: ReactNode
  className?: string
}

/** Every chart ships a table twin: values stay reachable without hovering or seeing colour. */
export function ChartCard({ title, description, legend, children, table, className }: ChartCardProps) {
  const [view, setView] = useState<'chart' | 'table'>('chart')
  return (
    <Card className={cn('flex flex-col', className)}>
      <CardHeader
        title={title}
        description={description}
        action={
          <SegmentedControl
            label={`${title} view`}
            value={view}
            onChange={setView}
            options={[
              { value: 'chart', label: <span className="sr-only sm:not-sr-only">Chart</span>, icon: <ChartColumn className="size-3.5" aria-hidden /> },
              { value: 'table', label: <span className="sr-only sm:not-sr-only">Table</span>, icon: <Table2 className="size-3.5" aria-hidden /> },
            ]}
          />
        }
      />
      {legend && view === 'chart' && <div className="px-5 pt-3">{legend}</div>}
      <div className="flex-1 px-3 pb-4 pt-3">{view === 'chart' ? children : <div className="overflow-x-auto px-2 scrollbar-thin">{table}</div>}</div>
    </Card>
  )
}

export function DataTable({ head, rows }: { head: ReactNode[]; rows: ReactNode[][] }) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-line text-left text-xs text-fg-muted">
          {head.map((cell, index) => (
            <th key={index} className={cn('py-2 pr-4 font-medium', index > 0 && 'text-right')}>
              {cell}
            </th>
          ))}
        </tr>
      </thead>
      <tbody className="divide-y divide-line">
        {rows.map((row, rowIndex) => (
          <tr key={rowIndex}>
            {row.map((cell, index) => (
              <td key={index} className={cn('py-2 pr-4 text-fg-2', index > 0 && 'tabular text-right')}>
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}
