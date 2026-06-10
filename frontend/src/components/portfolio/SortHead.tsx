import { useState } from 'react'
import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react'
import type { Column } from '@tanstack/react-table'
import { cn } from '@/lib/utils'

function SortIcon({ sorted }: { sorted: false | 'asc' | 'desc' }) {
  if (sorted === 'asc') return <ChevronUp className="h-3.5 w-3.5 text-blue-500 shrink-0" />
  if (sorted === 'desc') return <ChevronDown className="h-3.5 w-3.5 text-blue-500 shrink-0" />
  return <ChevronsUpDown className="h-3.5 w-3.5 opacity-30 shrink-0 group-hover:opacity-60 transition-opacity" />
}

export function SortHead({
  column,
  children,
  right = false,
  tooltip,
}: {
  column: Column<any, any>
  children: React.ReactNode
  right?: boolean
  tooltip?: string
}) {
  const [show, setShow] = useState(false)
  return (
    <div className={cn('relative inline-flex', right && 'w-full justify-end')}>
      <button
        className="group flex items-center gap-1 font-medium transition-colors hover:text-slate-700 leading-tight"
        onClick={column.getToggleSortingHandler()}
        onMouseEnter={() => tooltip && setShow(true)}
        onMouseLeave={() => setShow(false)}
      >
        {children}
        <SortIcon sorted={column.getIsSorted()} />
      </button>
      {show && tooltip && (
        <div className="absolute top-full left-1/2 -translate-x-1/2 mt-1 z-50 pointer-events-none">
          <div className="mx-auto w-fit border-[5px] border-transparent border-b-slate-800 -mb-px" />
          <div className="px-2.5 py-1.5 text-xs text-white bg-slate-800 rounded-md whitespace-nowrap shadow-lg">
            {tooltip}
          </div>
        </div>
      )}
    </div>
  )
}
