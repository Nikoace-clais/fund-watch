import { useMemo } from 'react'
import { BookOpen, Trash2 } from 'lucide-react'
import type { ColumnDef } from '@tanstack/react-table'
import { cn, formatPercent } from '@/lib/utils'
import { useColor } from '@/lib/color-context'
import { SortHead } from './SortHead'
import { FundTableCard, nameColumn, selectColumn } from './FundTableCard'

export type WatchOnlyItem = {
  code: string
  name?: string
  gszzl?: number
  gsz?: number
}

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

  const columns = useMemo<ColumnDef<WatchOnlyItem>[]>(
    () => [
      selectColumn(),
      nameColumn(),
      {
        id: 'gsz',
        accessorKey: 'gsz',
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
      },
      {
        id: 'gszzl',
        accessorKey: 'gszzl',
        size: 110,
        header: ({ column }) => (
          <SortHead
            column={column}
            right
            tooltip="按今日估算涨跌幅从高到低排序"
          >
            <span className="text-right leading-tight">日涨跌幅</span>
          </SortHead>
        ),
        cell: ({ row }) => {
          const v = row.original.gszzl
          return (
            <div className="text-right">
              {v != null ? (
                <p className={cn('text-sm font-medium', colorFor(v))}>
                  {formatPercent(v)}
                </p>
              ) : (
                <p className="text-sm text-slate-300">—</p>
              )}
            </div>
          )
        },
      },
      {
        id: 'actions',
        size: 80,
        header: () => <div className="text-center font-medium">操作</div>,
        cell: ({ row }) => {
          const it = row.original
          return (
            <div className="flex items-center justify-center gap-1">
              <button
                onClick={() =>
                  onEditHolding({ code: it.code, name: it.name, nav: it.gsz })
                }
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
      },
    ],
    [colorFor, onEditHolding, onDelete, deleting],
  )

  return (
    <FundTableCard
      title="自选（未持仓）"
      items={items}
      columns={columns}
      initialSorting={[{ id: 'gszzl', desc: true }]}
      batchDeleting={batchDeleting}
      onBatchDelete={onBatchDelete}
      cellPadding="px-6"
    />
  )
}
