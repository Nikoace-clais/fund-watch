import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import { BookOpen, History, Trash2 } from 'lucide-react'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  createColumnHelper,
  type SortingState,
  type RowSelectionState,
} from '@tanstack/react-table'
import type { PortfolioItem } from '@/lib/api'
import { cn, formatCNY, formatCNYSigned, formatPercent } from '@/lib/utils'
import { useColor } from '@/lib/color-context'
import { Checkbox } from '../Checkbox'
import { SortHead } from './SortHead'
import { BatchBar } from './BatchBar'
import { DataTable } from './DataTable'

const helper = createColumnHelper<PortfolioItem>()

export function HoldingsTable({
  items,
  totalCurrent,
  deleting,
  batchDeleting,
  onViewTx,
  onEditHolding,
  onDelete,
  onBatchDelete,
}: {
  items: PortfolioItem[]
  totalCurrent: number
  deleting: string | null
  batchDeleting: boolean
  onViewTx: (code: string, name?: string) => void
  onEditHolding: (h: { code: string; name?: string; nav?: number }) => void
  onDelete: (code: string, name?: string) => void
  onBatchDelete: (codes: string[], clearSelection: () => void) => void
}) {
  const { colorFor } = useColor()
  const [sorting, setSorting] = useState<SortingState>([{ id: 'current_value', desc: true }])
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
              <div className="flex items-center gap-1.5">
                <Link to={`/funds/${it.code}`} className="font-medium text-slate-900 hover:text-blue-600 leading-snug">
                  {it.name || it.code}
                </Link>
                {it.is_imported && (
                  <span className="text-xs px-1 py-0.5 rounded bg-amber-50 text-amber-600 border border-amber-200 shrink-0">导入</span>
                )}
              </div>
              <p className="text-xs text-slate-400 mt-0.5">{it.code}</p>
            </div>
          )
        },
        sortingFn: (a, b) =>
          (a.original.name || a.original.code).localeCompare(b.original.name || b.original.code, 'zh-CN'),
      }),
      helper.accessor((row) => (row.nav != null ? parseFloat(row.nav) : null), {
        id: 'nav',
        size: 110,
        header: ({ column }) => (
          <SortHead column={column} right tooltip="按当前估算净值从高到低排序">
            <span className="text-right leading-tight">
              估算净值<br />份额
            </span>
          </SortHead>
        ),
        cell: ({ row }) => {
          const it = row.original
          return (
            <div className="text-right">
              {it.nav != null
                ? <p className="text-slate-800">{parseFloat(it.nav).toFixed(4)}</p>
                : <p className="text-slate-300">—</p>}
              {it.shares != null
                ? <p className="text-xs text-slate-400 mt-0.5">{parseFloat(it.shares).toFixed(2)} 份</p>
                : <p className="text-xs text-slate-300 mt-0.5">—</p>}
            </div>
          )
        },
      }),
      helper.accessor((row) => parseFloat(row.current_value), {
        id: 'current_value',
        size: 120,
        header: ({ column }) => (
          <SortHead column={column} right tooltip="按持仓市值从高到低排序">
            <span className="text-right leading-tight">
              持仓金额<br />占比
            </span>
          </SortHead>
        ),
        cell: ({ row }) => {
          const cv = parseFloat(row.original.current_value)
          const pct = totalCurrent > 0 ? (cv / totalCurrent) * 100 : 0
          return (
            <div className="text-right">
              <p className="text-slate-800">{formatCNY(cv)}</p>
              <p className="text-xs text-slate-400 mt-0.5">{pct.toFixed(1)}%</p>
            </div>
          )
        },
      }),
      helper.accessor('daily_change', {
        size: 120,
        header: ({ column }) => (
          <SortHead column={column} right tooltip="按今日估算涨跌幅从高到低排序">
            <span className="text-right leading-tight">
              今日收益<br />涨跌幅
            </span>
          </SortHead>
        ),
        cell: ({ row }) => {
          const it = row.original
          const dr = parseFloat(it.daily_return)
          return it.is_imported ? (
            <p className="text-right text-slate-300">—</p>
          ) : (
            <div className="text-right">
              <p className={cn('font-medium', colorFor(dr))}>{formatCNYSigned(dr)}</p>
              <p className={cn('text-xs mt-0.5', colorFor(it.daily_change))}>{formatPercent(it.daily_change)}</p>
            </div>
          )
        },
      }),
      helper.accessor((row) => (row.return_rate != null ? parseFloat(row.return_rate) : null), {
        id: 'return_rate',
        size: 110,
        header: ({ column }) => (
          <SortHead column={column} right tooltip="按累计收益率从高到低排序">
            <span className="text-right leading-tight">
              累计收益<br />收益率
            </span>
          </SortHead>
        ),
        cell: ({ row }) => {
          const it = row.original
          const tr = parseFloat(it.total_return)
          const rr = it.return_rate != null ? parseFloat(it.return_rate) : null
          const cumRet = it.imported_cumulative_return != null ? parseFloat(it.imported_cumulative_return) : null
          return (
            <div className="text-right">
              <p className={cn('font-medium', colorFor(tr))}>{formatCNYSigned(tr)}</p>
              {it.is_imported && cumRet != null
                ? <p className="text-xs text-slate-400 mt-0.5">累计 {formatCNYSigned(cumRet)}</p>
                : rr != null
                  ? <p className={cn('text-xs mt-0.5', colorFor(rr))}>{formatPercent(rr)}</p>
                  : null}
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
                onClick={() => onViewTx(it.code, it.name)}
                className="p-1.5 rounded-md text-slate-400 hover:text-violet-500 hover:bg-violet-50 transition-colors"
                title="交易记录"
              >
                <History className="h-4 w-4" />
              </button>
              <button
                onClick={() => onEditHolding({ code: it.code, name: it.name, nav: it.nav != null ? parseFloat(it.nav) : undefined })}
                className="p-1.5 rounded-md text-slate-400 hover:text-blue-500 hover:bg-blue-50 transition-colors"
                title="记录交易"
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
    [colorFor, totalCurrent, onViewTx, onEditHolding, onDelete, deleting],
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
    <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-100">
        <h2 className="text-lg font-semibold text-slate-800">持仓明细</h2>
      </div>

      <BatchBar
        count={selectedCodes.length}
        onDelete={() => onBatchDelete(selectedCodes, () => setSelection({}))}
        onClear={() => setSelection({})}
        deleting={batchDeleting}
      />

      <DataTable table={table} />
    </div>
  )
}
