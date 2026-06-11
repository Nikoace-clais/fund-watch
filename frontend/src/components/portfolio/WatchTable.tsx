import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import { BookOpen, Trash2 } from 'lucide-react'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  createColumnHelper,
  type SortingState,
  type RowSelectionState,
} from '@tanstack/react-table'
import { cn, formatPercent } from '@/lib/utils'
import { useColor } from '@/lib/color-context'
import { Checkbox } from './Checkbox'
import { SortHead } from './SortHead'
import { BatchBar } from './BatchBar'
import { DataTable } from './DataTable'

export type WatchOnlyItem = {
  code: string
  name?: string
  gszzl?: number
  gsz?: number
}

const helper = createColumnHelper<WatchOnlyItem>()

export function WatchTable({
  items,
  deleting,
  batchDeleting,
  onEditHolding,
  onDelete,
  onBatchDelete,
}: {
  items: WatchOnlyItem[]
  deleting: string | null
  batchDeleting: boolean
  onEditHolding: (h: { code: string; name?: string; nav?: number }) => void
  onDelete: (code: string, name?: string) => void
  onBatchDelete: (codes: string[], clearSelection: () => void) => void
}) {
  const { colorFor } = useColor()
  const [sorting, setSorting] = useState<SortingState>([{ id: 'gszzl', desc: true }])
  const [selection, setSelection] = useState<RowSelectionState>({})

  const columns = useMemo(
    () => [
      helper.display({
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
      }),
      helper.accessor((row) => row.name || row.code, {
        id: 'name',
        header: ({ column }) => (
          <SortHead column={column} tooltip="按基金名称首字母排序">基金名称</SortHead>
        ),
        cell: ({ row }) => {
          const it = row.original
          return (
            <div>
              <Link to={`/funds/${it.code}`} className="text-sm font-medium text-slate-900 hover:text-blue-600">
                {it.name || it.code}
              </Link>
              <p className="text-xs text-slate-400 mt-0.5">{it.code}</p>
            </div>
          )
        },
        sortingFn: (a, b) =>
          (a.original.name || a.original.code).localeCompare(b.original.name || b.original.code, 'zh-CN'),
      }),
      helper.accessor('gsz', {
        size: 120,
        header: ({ column }) => (
          <SortHead column={column} right tooltip="按当前估算净值从高到低排序">
            <span className="text-right leading-tight">估算净值</span>
          </SortHead>
        ),
        cell: ({ row }) => (
          <div className="text-right">
            <p className="text-sm text-slate-800">
              {row.original.gsz != null ? row.original.gsz.toFixed(4) : '—'}
            </p>
          </div>
        ),
      }),
      helper.accessor('gszzl', {
        size: 110,
        header: ({ column }) => (
          <SortHead column={column} right tooltip="按今日估算涨跌幅从高到低排序">
            <span className="text-right leading-tight">日涨跌幅</span>
          </SortHead>
        ),
        cell: ({ row }) => {
          const v = row.original.gszzl
          return (
            <div className="text-right">
              {v != null
                ? <p className={cn('text-sm font-medium', colorFor(v))}>{formatPercent(v)}</p>
                : <p className="text-sm text-slate-300">—</p>}
            </div>
          )
        },
      }),
      helper.display({
        id: 'actions',
        size: 80,
        header: () => <div className="text-center font-medium">操作</div>,
        cell: ({ row }) => {
          const it = row.original
          return (
            <div className="flex items-center justify-center gap-1">
              <button
                onClick={() => onEditHolding({ code: it.code, name: it.name, nav: it.gsz })}
                className="p-1.5 rounded-md text-slate-400 hover:text-blue-500 hover:bg-blue-50 transition-colors"
                title="记录持仓"
              >
                <BookOpen className="h-4 w-4" />
              </button>
              <button
                onClick={() => onDelete(it.code, it.name)}
                disabled={deleting === it.code}
                className={cn(
                  'p-1.5 rounded-md text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors',
                  deleting === it.code && 'opacity-50 cursor-not-allowed',
                )}
                title="删除基金"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          )
        },
      }),
    ],
    [colorFor, onEditHolding, onDelete, deleting],
  )

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
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-100">
        <h2 className="text-lg font-semibold text-slate-800">自选（未持仓）</h2>
      </div>

      <BatchBar
        count={selectedCodes.length}
        onDelete={() => onBatchDelete(selectedCodes, () => setSelection({}))}
        onClear={() => setSelection({})}
        deleting={batchDeleting}
      />

      <DataTable table={table} cellPadding="px-6" />
    </div>
  )
}
