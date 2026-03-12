import { useEffect, useState, useCallback, useMemo, useRef } from 'react'
import { Link } from 'react-router'
import {
  PieChart as PieChartIcon,
  TrendingUp,
  Plus,
  Trash2,
  BookOpen,
  ChevronUp,
  ChevronDown,
  ChevronsUpDown,
  History,
  X,
} from 'lucide-react'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  createColumnHelper,
  flexRender,
  type SortingState,
  type Column,
  type RowSelectionState,
} from '@tanstack/react-table'
import { AddFundModal } from '@/components/AddFundModal'
import { HoldingEditModal } from '@/components/HoldingEditModal'
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
  AreaChart, Area, XAxis, YAxis, CartesianGrid, ReferenceLine,
} from 'recharts'
import { fetchPortfolioSummary, fetchFundsOverview, deleteFund, fetchPortfolioHistory, fetchTransactions, deleteTransaction, type Transaction } from '@/lib/api'
import { cn, formatCNY, formatPercent } from '@/lib/utils'
import { useColor } from '@/lib/color-context'

/* ---------- types ---------- */
type WatchOnlyItem = {
  code: string
  name?: string
  gszzl?: number
  gsz?: number
}

type PortfolioItem = {
  code: string
  name?: string
  shares: string | null
  nav: string | null
  daily_change: number
  current_value: string
  daily_return: string
  total_cost: string | null
  total_return: string
  return_rate: string | null
  imported_cumulative_return?: string
  is_imported?: boolean
}

type PortfolioSummary = {
  total_current: string
  total_cost: string
  total_daily_return: string
  total_return: string
  total_return_rate: string
  fund_count: number
  items: PortfolioItem[]
}

const PIE_COLORS = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899']

/* ---------- column helpers ---------- */
const holdingHelper = createColumnHelper<PortfolioItem>()
const watchHelper = createColumnHelper<WatchOnlyItem>()

/* ---------- Checkbox (supports indeterminate) ---------- */
function Checkbox({
  checked,
  indeterminate,
  onChange,
}: {
  checked: boolean
  indeterminate?: boolean
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void
}) {
  const ref = useRef<HTMLInputElement>(null)
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = indeterminate ?? false
  }, [indeterminate])
  return (
    <input
      ref={ref}
      type="checkbox"
      checked={checked}
      onChange={onChange}
      className="h-4 w-4 rounded border-slate-300 text-blue-600 cursor-pointer accent-blue-600"
    />
  )
}

/* ---------- Sort + Tooltip header ---------- */
function SortHead({
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

function SortIcon({ sorted }: { sorted: false | 'asc' | 'desc' }) {
  if (sorted === 'asc') return <ChevronUp className="h-3.5 w-3.5 text-blue-500 shrink-0" />
  if (sorted === 'desc') return <ChevronDown className="h-3.5 w-3.5 text-blue-500 shrink-0" />
  return <ChevronsUpDown className="h-3.5 w-3.5 opacity-30 shrink-0 group-hover:opacity-60 transition-opacity" />
}

/* ---------- Batch action bar ---------- */
function BatchBar({
  count,
  onDelete,
  onClear,
  deleting,
}: {
  count: number
  onDelete: () => void
  onClear: () => void
  deleting: boolean
}) {
  if (count === 0) return null
  return (
    <div className="flex items-center gap-4 px-6 py-2.5 bg-blue-50 border-b border-blue-100">
      <span className="text-sm font-medium text-blue-700">已选 {count} 只基金</span>
      <div className="flex-1" />
      <button
        onClick={onDelete}
        disabled={deleting}
        className="inline-flex items-center gap-1.5 text-sm font-medium text-red-600 hover:text-red-700 disabled:opacity-50 transition-colors"
      >
        <Trash2 className="h-3.5 w-3.5" />
        删除选中
      </button>
      <button
        onClick={onClear}
        className="text-sm text-slate-500 hover:text-slate-700 transition-colors"
      >
        取消
      </button>
    </div>
  )
}

/* ---------- TransactionModal ---------- */
function TransactionModal({
  code, name, onClose, onChanged, onAddTx,
}: {
  code: string
  name?: string
  onClose: () => void
  onChanged: () => void
  onAddTx: () => void
}) {
  const [items, setItems] = useState<Transaction[]>([])
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState<number | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    fetchTransactions(code)
      .then((r) => setItems(r.items))
      .finally(() => setLoading(false))
  }, [code])

  useEffect(() => { load() }, [load])

  const handleDelete = async (id: number) => {
    if (!confirm('确认删除该条交易记录？')) return
    setDeleting(id)
    try {
      await deleteTransaction(id)
      onChanged()
      load()
    } finally {
      setDeleting(null)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 flex flex-col max-h-[80vh]">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 shrink-0">
          <div>
            <h2 className="text-base font-semibold text-slate-900">交易记录</h2>
            <p className="text-xs text-slate-400 mt-0.5">{name || code} · {code}</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={onAddTx}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-500 text-white text-sm hover:bg-blue-600 transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              记录交易
            </button>
            <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 transition-colors">
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        <div className="overflow-y-auto flex-1 px-6 py-4">
          {loading ? (
            <p className="text-center text-slate-400 py-8 text-sm">加载中...</p>
          ) : items.length === 0 ? (
            <p className="text-center text-slate-400 py-8 text-sm">暂无交易记录</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-slate-400 border-b border-slate-100">
                  <th className="text-left pb-2 font-medium">日期</th>
                  <th className="text-center pb-2 font-medium">方向</th>
                  <th className="text-right pb-2 font-medium">净值</th>
                  <th className="text-right pb-2 font-medium">份额</th>
                  <th className="text-right pb-2 font-medium">金额</th>
                  <th className="text-center pb-2 font-medium">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {items.map((tx) => (
                  <tr key={tx.id} className="hover:bg-slate-50">
                    <td className="py-2.5 text-slate-600">{tx.trade_date}</td>
                    <td className="py-2.5 text-center">
                      <span className={cn(
                        'inline-block px-2 py-0.5 rounded-full text-xs font-medium',
                        tx.direction === 'buy' ? 'bg-red-50 text-red-600' : 'bg-green-50 text-green-600',
                      )}>
                        {tx.direction === 'buy' ? '买入' : '卖出'}
                      </span>
                    </td>
                    <td className="py-2.5 text-right text-slate-700">{parseFloat(tx.nav).toFixed(4)}</td>
                    <td className="py-2.5 text-right text-slate-700">{parseFloat(tx.shares).toFixed(2)}</td>
                    <td className="py-2.5 text-right text-slate-700">{formatCNY(parseFloat(tx.amount))}</td>
                    <td className="py-2.5 text-center">
                      <button
                        onClick={() => handleDelete(tx.id)}
                        disabled={deleting === tx.id}
                        className="p-1 rounded text-slate-300 hover:text-red-500 hover:bg-red-50 transition-colors disabled:opacity-50"
                        title="删除"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}

/* ---------- component ---------- */
export function Portfolio() {
  const { colorFor } = useColor()
  const [summary, setSummary] = useState<PortfolioSummary | null>(null)
  const [watchOnly, setWatchOnly] = useState<WatchOnlyItem[]>([])
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [batchDeleting, setBatchDeleting] = useState(false)
  const [showAddModal, setShowAddModal] = useState(false)
  const [holdingEdit, setHoldingEdit] = useState<{ code: string; name?: string; nav?: number } | null>(null)
  const [txView, setTxView] = useState<{ code: string; name?: string } | null>(null)
  const [holdingSorting, setHoldingSorting] = useState<SortingState>([{ id: 'current_value', desc: true }])
  const [watchSorting, setWatchSorting] = useState<SortingState>([{ id: 'gszzl', desc: true }])
  const [holdingSelection, setHoldingSelection] = useState<RowSelectionState>({})
  const [watchSelection, setWatchSelection] = useState<RowSelectionState>({})

  const [trendHistory, setTrendHistory] = useState<Array<{ date: string; total_value: number }>>([])
  const [trendRange, setTrendRange] = useState<21 | 63 | 126 | 252>(63)
  const [trendLoading, setTrendLoading] = useState(false)

  const loadData = useCallback(async () => {
    try {
      const [ps, ov] = await Promise.allSettled([
        fetchPortfolioSummary(),
        fetchFundsOverview(),
      ])
      const portfolioData = ps.status === 'fulfilled' ? ps.value : null
      if (portfolioData) setSummary(portfolioData)

      if (ov.status === 'fulfilled') {
        const holdingCodes = new Set((portfolioData?.items ?? []).map((i) => i.code))
        setWatchOnly(
          ov.value.items
            .filter((i) => !holdingCodes.has(i.fund.code))
            .map((i) => ({
              code: i.fund.code,
              name: i.latest?.name || i.fund.name,
              gszzl: i.latest?.gszzl,
              gsz: i.latest?.gsz ?? i.latest?.dwjz,
            })),
        )
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  useEffect(() => {
    setTrendLoading(true)
    fetchPortfolioHistory(trendRange)
      .then((res) => setTrendHistory(res.history))
      .catch(() => setTrendHistory([]))
      .finally(() => setTrendLoading(false))
  }, [trendRange])

  const handleDelete = useCallback(
    async (code: string, name?: string) => {
      if (!confirm(`确认删除基金 ${name || code}?`)) return
      setDeleting(code)
      try { await deleteFund(code); await loadData() }
      finally { setDeleting(null) }
    },
    [loadData],
  )

  const handleBatchDelete = useCallback(
    async (codes: string[], clearSelection: () => void) => {
      if (!confirm(`确认删除选中的 ${codes.length} 只基金？此操作不可撤销。`)) return
      setBatchDeleting(true)
      try {
        await Promise.all(codes.map((c) => deleteFund(c)))
        await loadData()
        clearSelection()
      } finally {
        setBatchDeleting(false)
      }
    },
    [loadData],
  )

  /* derived */
  const items = summary?.items ?? []
  const totalCurrent = parseFloat(summary?.total_current ?? '0')
  const totalCost = parseFloat(summary?.total_cost ?? '0')
  const totalDailyReturn = parseFloat(summary?.total_daily_return ?? '0')
  const totalReturn = parseFloat(summary?.total_return ?? '0')
  const totalReturnRate = parseFloat(summary?.total_return_rate ?? '0')
  const fundCount = summary?.fund_count ?? 0
  const hasItems = items.length > 0

  const bestFund = items.length
    ? items.reduce((best, it) =>
        parseFloat(it.return_rate ?? String(Number.NEGATIVE_INFINITY)) >
        parseFloat(best.return_rate ?? String(Number.NEGATIVE_INFINITY)) ? it : best)
    : null

  const dailyReturnRate =
    totalCurrent - totalDailyReturn !== 0
      ? (totalDailyReturn / (totalCurrent - totalDailyReturn)) * 100
      : 0

  const pieData = items.map((it) => ({ name: it.name || it.code, value: parseFloat(it.current_value) }))

  /* ---------- holdings columns ---------- */
  const holdingColumns = useMemo(
    () => [
      holdingHelper.display({
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
          <Checkbox
            checked={row.getIsSelected()}
            onChange={row.getToggleSelectedHandler()}
          />
        ),
      }),
      holdingHelper.accessor((row) => row.name || row.code, {
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
      holdingHelper.accessor((row) => (row.nav != null ? parseFloat(row.nav) : null), {
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
      holdingHelper.accessor((row) => parseFloat(row.current_value), {
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
      holdingHelper.accessor('daily_change', {
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
              <p className={cn('font-medium', colorFor(dr))}>{dr > 0 ? '+' : ''}{formatCNY(dr)}</p>
              <p className={cn('text-xs mt-0.5', colorFor(it.daily_change))}>{formatPercent(it.daily_change)}</p>
            </div>
          )
        },
      }),
      holdingHelper.accessor((row) => (row.return_rate != null ? parseFloat(row.return_rate) : null), {
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
              <p className={cn('font-medium', colorFor(tr))}>{tr > 0 ? '+' : ''}{formatCNY(tr)}</p>
              {it.is_imported && cumRet != null
                ? <p className="text-xs text-slate-400 mt-0.5">累计 {cumRet > 0 ? '+' : ''}{formatCNY(cumRet)}</p>
                : rr != null
                  ? <p className={cn('text-xs mt-0.5', colorFor(rr))}>{formatPercent(rr)}</p>
                  : null}
            </div>
          )
        },
      }),
      holdingHelper.display({
        id: 'actions',
        size: 80,
        header: () => <div className="text-center font-medium">操作</div>,
        cell: ({ row }) => {
          const it = row.original
          return (
            <div className="flex items-center justify-center gap-1">
              <button
                onClick={() => setTxView({ code: it.code, name: it.name })}
                className="p-1.5 rounded-md text-slate-400 hover:text-violet-500 hover:bg-violet-50 transition-colors"
                title="交易记录"
              >
                <History className="h-4 w-4" />
              </button>
              <button
                onClick={() => setHoldingEdit({ code: it.code, name: it.name, nav: it.nav != null ? parseFloat(it.nav) : undefined })}
                className="p-1.5 rounded-md text-slate-400 hover:text-blue-500 hover:bg-blue-50 transition-colors"
                title="记录交易"
              >
                <BookOpen className="h-4 w-4" />
              </button>
              <button
                onClick={() => handleDelete(it.code, it.name)}
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
    [colorFor, totalCurrent, setHoldingEdit, handleDelete, deleting],
  )

  /* ---------- watch-only columns ---------- */
  const watchColumns = useMemo(
    () => [
      watchHelper.display({
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
          <Checkbox
            checked={row.getIsSelected()}
            onChange={row.getToggleSelectedHandler()}
          />
        ),
      }),
      watchHelper.accessor((row) => row.name || row.code, {
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
      watchHelper.accessor('gsz', {
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
      watchHelper.accessor('gszzl', {
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
      watchHelper.display({
        id: 'actions',
        size: 80,
        header: () => <div className="text-center font-medium">操作</div>,
        cell: ({ row }) => {
          const it = row.original
          return (
            <div className="flex items-center justify-center gap-1">
              <button
                onClick={() => setHoldingEdit({ code: it.code, name: it.name, nav: it.gsz })}
                className="p-1.5 rounded-md text-slate-400 hover:text-blue-500 hover:bg-blue-50 transition-colors"
                title="记录持仓"
              >
                <BookOpen className="h-4 w-4" />
              </button>
              <button
                onClick={() => handleDelete(it.code, it.name)}
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
    [colorFor, setHoldingEdit, handleDelete, deleting],
  )

  /* ---------- table instances ---------- */
  const holdingTable = useReactTable({
    data: items,
    columns: holdingColumns,
    state: { sorting: holdingSorting, rowSelection: holdingSelection },
    onSortingChange: setHoldingSorting,
    onRowSelectionChange: setHoldingSelection,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    enableRowSelection: true,
    getRowId: (row) => row.code,
    sortDescFirst: true,
    ...({ sortUndefined: 'last' } as object),
  })

  const watchTable = useReactTable({
    data: watchOnly,
    columns: watchColumns,
    state: { sorting: watchSorting, rowSelection: watchSelection },
    onSortingChange: setWatchSorting,
    onRowSelectionChange: setWatchSelection,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    enableRowSelection: true,
    getRowId: (row) => row.code,
    sortDescFirst: true,
    ...({ sortUndefined: 'last' } as object),
  })

  const holdingSelectedCodes = holdingTable.getSelectedRowModel().rows.map((r) => r.original.code)
  const watchSelectedCodes = watchTable.getSelectedRowModel().rows.map((r) => r.original.code)

  /* ---- loading ---- */
  if (loading) {
    return <div className="flex items-center justify-center py-32 text-slate-400">加载中...</div>
  }

  return (
    <div className="space-y-8">
      {/* ---- Header ---- */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">自选基金与持仓</h1>
          <p className="text-sm text-slate-500 mt-1">管理你的基金组合与持仓情况</p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 transition-colors shadow-sm"
        >
          <Plus className="h-4 w-4" />
          添加基金
        </button>
      </div>

      <AddFundModal open={showAddModal} onClose={() => setShowAddModal(false)} onAdded={loadData} />
      <HoldingEditModal
        open={holdingEdit !== null}
        onClose={() => setHoldingEdit(null)}
        onSaved={loadData}
        code={holdingEdit?.code ?? ''}
        name={holdingEdit?.name}
        defaultNav={holdingEdit?.nav}
      />

      {txView && (
        <TransactionModal
          code={txView.code}
          name={txView.name}
          onClose={() => setTxView(null)}
          onChanged={() => { loadData(); }}
          onAddTx={() => { setTxView(null); setHoldingEdit({ code: txView.code, name: txView.name }); }}
        />
      )}

      {/* ---- Empty state ---- */}
      {!hasItems && watchOnly.length === 0 && (
        <div className="flex flex-col items-center justify-center py-32 text-center">
          <div className="rounded-full bg-slate-100 p-6 mb-6">
            <PieChartIcon className="h-10 w-10 text-slate-400" />
          </div>
          <h2 className="text-xl font-semibold text-slate-700 mb-2">暂无自选基金</h2>
          <p className="text-sm text-slate-400 mb-6">点击上方"添加基金"按钮，通过搜索、输入代码或批量导入添加基金</p>
          <button
            onClick={() => setShowAddModal(true)}
            className="inline-flex items-center gap-1.5 text-blue-600 hover:text-blue-700 font-medium text-sm"
          >
            <Plus className="h-4 w-4" /> 立即添加
          </button>
        </div>
      )}

      {/* ---- Stats cards ---- */}
      {hasItems && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-xl p-6 shadow-lg text-white">
              <p className="text-sm text-slate-300 mb-1">总资产(预估)</p>
              <p className="text-2xl font-bold">{formatCNY(totalCurrent)}</p>
              <p className="text-xs text-slate-400 mt-2">总投入成本: {formatCNY(totalCost)}</p>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
              <p className="text-sm text-slate-500 mb-1">今日收益(估算)</p>
              <p className={cn('text-2xl font-bold', colorFor(totalDailyReturn))}>
                {totalDailyReturn > 0 ? '+' : ''}{formatCNY(totalDailyReturn)}
              </p>
              <p className={cn('text-xs mt-2', colorFor(dailyReturnRate))}>今日收益率: {formatPercent(dailyReturnRate)}</p>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
              <p className="text-sm text-slate-500 mb-1">累计收益</p>
              <p className={cn('text-2xl font-bold', colorFor(totalReturn))}>
                {totalReturn > 0 ? '+' : ''}{formatCNY(totalReturn)}
              </p>
              <p className={cn('text-xs mt-2', colorFor(totalReturnRate))}>累计收益率: {formatPercent(totalReturnRate)}</p>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
              <div className="flex items-center gap-2 text-slate-500 text-sm mb-1">
                <PieChartIcon className="h-4 w-4" />自选基金数量
              </div>
              <p className="text-2xl font-bold text-slate-900">{fundCount}</p>
              {bestFund && (
                <p className="text-xs text-slate-400 mt-2 truncate">
                  表现最好: {bestFund.name || bestFund.code}{' '}
                  <span className={colorFor(parseFloat(bestFund.return_rate ?? '0'))}>
                    {formatPercent(parseFloat(bestFund.return_rate ?? '0'))}
                  </span>
                </p>
              )}
            </div>
          </div>

          {/* ---- Portfolio trend chart ---- */}
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-slate-700" />
                <h2 className="text-lg font-semibold text-slate-800">组合资产走势</h2>
              </div>
              <div className="flex items-center gap-1">
                {([21, 63, 126, 252] as const).map((r) => (
                  <button
                    key={r}
                    onClick={() => setTrendRange(r)}
                    className={cn(
                      'px-3 py-1 rounded-md text-xs font-medium transition-colors',
                      trendRange === r
                        ? 'bg-blue-600 text-white'
                        : 'text-slate-500 hover:text-slate-700 hover:bg-slate-100',
                    )}
                  >
                    {r === 21 ? '1月' : r === 63 ? '3月' : r === 126 ? '6月' : '1年'}
                  </button>
                ))}
              </div>
            </div>

            {trendLoading ? (
              <div className="h-52 flex items-center justify-center text-slate-400 text-sm">加载中...</div>
            ) : trendHistory.length < 2 ? (
              <div className="h-52 flex items-center justify-center text-slate-400 text-sm">
                暂无足够的历史数据，持仓交易记录后将自动展示
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={trendHistory} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="trendGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.18} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 11, fill: '#94a3b8' }}
                    tickLine={false}
                    axisLine={false}
                    interval="preserveStartEnd"
                    tickFormatter={(v: string) => v.slice(5)}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: '#94a3b8' }}
                    tickLine={false}
                    axisLine={false}
                    width={72}
                    tickFormatter={(v: number) => `¥${(v / 10000).toFixed(1)}万`}
                    domain={['auto', 'auto']}
                  />
                  <Tooltip
                    formatter={(value: number) => [formatCNY(value), '组合市值']}
                    labelStyle={{ fontSize: 12, color: '#475569' }}
                    contentStyle={{ borderRadius: 8, border: '1px solid #e2e8f0', fontSize: 12 }}
                  />
                  {totalCost > 0 && (
                    <ReferenceLine
                      y={totalCost}
                      stroke="#f59e0b"
                      strokeDasharray="5 4"
                      strokeWidth={1.5}
                      label={{ value: '成本', position: 'insideTopRight', fontSize: 11, fill: '#f59e0b' }}
                    />
                  )}
                  <Area
                    type="monotone"
                    dataKey="total_value"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    fill="url(#trendGrad)"
                    dot={false}
                    activeDot={{ r: 4, stroke: '#3b82f6', strokeWidth: 2, fill: '#fff' }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* ---- Holdings table + pie ---- */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            {/* Table 2/3 */}
            <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-100">
                <h2 className="text-lg font-semibold text-slate-800">持仓明细</h2>
              </div>

              <BatchBar
                count={holdingSelectedCodes.length}
                onDelete={() => handleBatchDelete(holdingSelectedCodes, () => setHoldingSelection({}))}
                onClear={() => setHoldingSelection({})}
                deleting={batchDeleting}
              />

              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <colgroup>
                    {holdingTable.getVisibleLeafColumns().map((col) => (
                      <col key={col.id} style={col.id !== 'name' ? { width: `${col.getSize()}px` } : undefined} />
                    ))}
                  </colgroup>
                  <thead>
                    {holdingTable.getHeaderGroups().map((hg) => (
                      <tr key={hg.id} className="bg-slate-50 text-slate-500 text-xs uppercase">
                        {hg.headers.map((header) => (
                          <th
                            key={header.id}
                            className={cn(
                              'px-4 py-3 align-middle',
                              header.column.id === 'name' || header.column.id === 'select'
                                ? 'text-left'
                                : 'text-right',
                              header.column.id === 'actions' && 'text-center',
                            )}
                          >
                            {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                          </th>
                        ))}
                      </tr>
                    ))}
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {holdingTable.getRowModel().rows.map((row) => (
                      <tr
                        key={row.id}
                        className={cn(
                          'transition-colors',
                          row.getIsSelected() ? 'bg-blue-50' : 'hover:bg-slate-50',
                        )}
                      >
                        {row.getVisibleCells().map((cell) => (
                          <td
                            key={cell.id}
                            className={cn(
                              'px-4 py-3',
                              cell.column.id === 'name' || cell.column.id === 'select'
                                ? 'text-left'
                                : 'text-right',
                              cell.column.id === 'actions' && 'text-center',
                            )}
                          >
                            {flexRender(cell.column.columnDef.cell, cell.getContext())}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Pie 1/3 */}
            <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
              <h2 className="text-lg font-semibold text-slate-800 mb-4">持仓分布</h2>
              <div className="relative">
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie data={pieData} cx="50%" cy="50%" innerRadius={60} outerRadius={90} dataKey="value" stroke="none">
                      {pieData.map((_, idx) => (
                        <Cell key={idx} fill={PIE_COLORS[idx % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(value: number) => formatCNY(value)} wrapperStyle={{ zIndex: 10 }} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                  <p className="text-xs text-slate-400">基金数量</p>
                  <p className="text-2xl font-bold text-slate-900">{fundCount}</p>
                </div>
              </div>
              <div className="mt-4 space-y-2">
                {items.map((it, idx) => {
                  const cv = parseFloat(it.current_value)
                  const pct = totalCurrent > 0 ? (cv / totalCurrent) * 100 : 0
                  return (
                    <div key={it.code} className="flex items-center justify-between text-sm">
                      <div className="flex items-center gap-2">
                        <span className="inline-block h-3 w-3 rounded-full shrink-0" style={{ backgroundColor: PIE_COLORS[idx % PIE_COLORS.length] }} />
                        <span className="text-slate-700 truncate max-w-[120px]">{it.name || it.code}</span>
                      </div>
                      <span className="text-slate-500 font-medium">{pct.toFixed(1)}%</span>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        </>
      )}

      {/* ---- Watch-only table ---- */}
      {watchOnly.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100">
            <h2 className="text-lg font-semibold text-slate-800">自选（未持仓）</h2>
          </div>

          <BatchBar
            count={watchSelectedCodes.length}
            onDelete={() => handleBatchDelete(watchSelectedCodes, () => setWatchSelection({}))}
            onClear={() => setWatchSelection({})}
            deleting={batchDeleting}
          />

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <colgroup>
                {watchTable.getVisibleLeafColumns().map((col) => (
                  <col key={col.id} style={col.id !== 'name' ? { width: `${col.getSize()}px` } : undefined} />
                ))}
              </colgroup>
              <thead>
                {watchTable.getHeaderGroups().map((hg) => (
                  <tr key={hg.id} className="bg-slate-50 text-slate-500 text-xs uppercase">
                    {hg.headers.map((header) => (
                      <th
                        key={header.id}
                        className={cn(
                          'px-6 py-3 align-middle',
                          header.column.id === 'name' || header.column.id === 'select'
                            ? 'text-left'
                            : 'text-right',
                          header.column.id === 'actions' && 'text-center',
                        )}
                      >
                        {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody className="divide-y divide-slate-100">
                {watchTable.getRowModel().rows.map((row) => (
                  <tr
                    key={row.id}
                    className={cn(
                      'transition-colors',
                      row.getIsSelected() ? 'bg-blue-50' : 'hover:bg-slate-50',
                    )}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td
                        key={cell.id}
                        className={cn(
                          'px-6 py-3',
                          cell.column.id === 'name' || cell.column.id === 'select'
                            ? 'text-left'
                            : 'text-right',
                          cell.column.id === 'actions' && 'text-center',
                        )}
                      >
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
