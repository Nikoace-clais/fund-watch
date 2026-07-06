import { useState, type ReactNode } from 'react'
import { Link } from 'react-router'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  type ColumnDef,
  type SortingState,
  type RowSelectionState,
} from '@tanstack/react-table'
import { cn } from '@/lib/utils'
import { Checkbox } from '../Checkbox'
import { SortHead } from './SortHead'
import { BatchBar } from './BatchBar'
import { DataTable } from './DataTable'

type FundRow = { code: string; name?: string }

/** 行首多选列（表头全选 + indeterminate）。 */
export function selectColumn<T extends FundRow>(): ColumnDef<T> {
  return {
    id: 'select',
    size: 44,
    header: ({ table }) => (
      <Checkbox
        checked={table.getIsAllRowsSelected()}
        indeterminate={table.getIsSomeRowsSelected()}
        onChange={table.getToggleAllRowsSelectedHandler()}
      />
    ),
    cell: ({ row }) => (
      <Checkbox checked={row.getIsSelected()} onChange={row.getToggleSelectedHandler()} />
    ),
  }
}

/** 基金名称列：详情链接 + 代码副标题，zh-CN 排序；extra 渲染名称旁的徽标。 */
export function nameColumn<T extends FundRow>(extra?: (row: T) => ReactNode): ColumnDef<T> {
  return {
    id: 'name',
    accessorFn: (row) => row.name || row.code,
    header: ({ column }) => (
      <SortHead column={column} tooltip="按基金名称首字母排序">基金名称</SortHead>
    ),
    cell: ({ row }) => {
      const it = row.original
      return (
        <div>
          <div className="flex items-center gap-1.5">
            <Link to={`/funds/${it.code}`} className="text-sm font-medium text-slate-900 hover:text-blue-600 leading-snug">
              {it.name || it.code}
            </Link>
            {extra?.(it)}
          </div>
          <p className="text-xs text-slate-400 mt-0.5">{it.code}</p>
        </div>
      )
    },
    sortingFn: (a, b) =>
      (a.original.name || a.original.code).localeCompare(b.original.name || b.original.code, 'zh-CN'),
  }
}

/** 基金表卡片壳：排序/多选状态 + BatchBar + DataTable，供持仓/自选两张表复用。 */
export function FundTableCard<T extends FundRow>({
  title,
  items,
  columns,
  initialSorting,
  batchDeleting,
  onBatchDelete,
  className,
  cellPadding,
}: {
  title: string
  items: T[]
  columns: ColumnDef<T>[]
  initialSorting: SortingState
  batchDeleting: boolean
  onBatchDelete: (codes: string[], clearSelection: () => void) => void
  className?: string
  cellPadding?: string
}) {
  const [sorting, setSorting] = useState<SortingState>(initialSorting)
  const [selection, setSelection] = useState<RowSelectionState>({})

  const table = useReactTable({
    data: items,
    columns,
    state: { sorting, rowSelection: selection },
    onSortingChange: setSorting,
    onRowSelectionChange: setSelection,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    enableRowSelection: true,
    getRowId: (row) => row.code,
    sortDescFirst: true,
    ...({ sortUndefined: 'last' } as object),
  })

  const selectedCodes = table.getSelectedRowModel().rows.map((r) => r.original.code)

  return (
    <div className={cn('bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden', className)}>
      <div className="px-6 py-4 border-b border-slate-100">
        <h2 className="text-lg font-semibold text-slate-800">{title}</h2>
      </div>

      <BatchBar
        count={selectedCodes.length}
        onDelete={() => onBatchDelete(selectedCodes, () => setSelection({}))}
        onClear={() => setSelection({})}
        deleting={batchDeleting}
      />

      <DataTable table={table} cellPadding={cellPadding} />
    </div>
  )
}
