import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router'
import {
  PieChart as PieChartIcon,
  TrendingUp,
  Plus,
  Trash2,
  BookOpen,
} from 'lucide-react'
import { AddFundModal } from '@/components/AddFundModal'
import { HoldingEditModal } from '@/components/HoldingEditModal'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts'
import { fetchPortfolioSummary, fetchFundsOverview, deleteFund } from '@/lib/api'

type WatchOnlyItem = {
  code: string
  name?: string
  gszzl?: number
  gsz?: number
}
import { cn, formatCNY, formatPercent } from '@/lib/utils'
import { useColor } from '@/lib/color-context'

/* ---------- types ---------- */
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

/* ---------- component ---------- */
export function Portfolio() {
  const { colorFor } = useColor()
  const [summary, setSummary] = useState<PortfolioSummary | null>(null)
  const [watchOnly, setWatchOnly] = useState<WatchOnlyItem[]>([])
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [showAddModal, setShowAddModal] = useState(false)
  const [holdingEdit, setHoldingEdit] = useState<{ code: string; name?: string; nav?: number } | null>(null)

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
        const watchOnlyItems = ov.value.items
          .filter((i) => !holdingCodes.has(i.fund.code))
          .map((i) => ({
            code: i.fund.code,
            name: i.latest?.name || i.fund.name,
            gszzl: i.latest?.gszzl,
            gsz: i.latest?.gsz ?? i.latest?.dwjz,
          }))
        setWatchOnly(watchOnlyItems)
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleDelete = async (code: string, name?: string) => {
    if (!confirm(`确认删除基金 ${name || code}?`)) return
    setDeleting(code)
    try {
      await deleteFund(code)
      await loadData()
    } finally {
      setDeleting(null)
    }
  }

  /* derived */
  const items = summary?.items ?? []
  const totalCurrent = parseFloat(summary?.total_current ?? '0')
  const totalCost = parseFloat(summary?.total_cost ?? '0')
  const totalDailyReturn = parseFloat(summary?.total_daily_return ?? '0')
  const totalReturn = parseFloat(summary?.total_return ?? '0')
  const totalReturnRate = parseFloat(summary?.total_return_rate ?? '0')
  const fundCount = summary?.fund_count ?? 0
  const hasItems = items.length > 0

  /* best performer */
  const bestFund = items.length
    ? items.reduce((best, it) =>
        parseFloat(it.return_rate) > parseFloat(best.return_rate) ? it : best,
      )
    : null

  /* daily return rate: totalDailyReturn / (totalCurrent - totalDailyReturn) */
  const dailyReturnRate =
    totalCurrent - totalDailyReturn !== 0
      ? (totalDailyReturn / (totalCurrent - totalDailyReturn)) * 100
      : 0

  /* pie data */
  const pieData = items.map((it) => ({
    name: it.name || it.code,
    value: parseFloat(it.current_value),
  }))

  /* ---- loading state ---- */
  if (loading) {
    return (
      <div className="flex items-center justify-center py-32 text-slate-400">
        加载中...
      </div>
    )
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
          className={cn(
            'inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium',
            'bg-blue-600 text-white hover:bg-blue-700 transition-colors shadow-sm',
          )}
        >
          <Plus className="h-4 w-4" />
          添加基金
        </button>
      </div>

      {/* ---- Add fund modal ---- */}
      <AddFundModal
        open={showAddModal}
        onClose={() => setShowAddModal(false)}
        onAdded={() => loadData()}
      />

      {/* ---- Holding edit modal ---- */}
      <HoldingEditModal
        open={holdingEdit !== null}
        onClose={() => setHoldingEdit(null)}
        onSaved={() => loadData()}
        code={holdingEdit?.code ?? ''}
        name={holdingEdit?.name}
        defaultNav={holdingEdit?.nav}
      />

      {/* ---- Empty state ---- */}
      {!hasItems && watchOnly.length === 0 && (
        <div className="flex flex-col items-center justify-center py-32 text-center">
          <div className="rounded-full bg-slate-100 p-6 mb-6">
            <PieChartIcon className="h-10 w-10 text-slate-400" />
          </div>
          <h2 className="text-xl font-semibold text-slate-700 mb-2">暂无自选基金</h2>
          <p className="text-sm text-slate-400 mb-6">
            点击上方"添加基金"按钮，通过搜索、输入代码或批量导入添加基金
          </p>
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
            {/* Total assets - dark card */}
            <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-xl p-6 shadow-lg text-white">
              <p className="text-sm text-slate-300 mb-1">总资产(预估)</p>
              <p className="text-2xl font-bold">{formatCNY(totalCurrent)}</p>
              <p className="text-xs text-slate-400 mt-2">
                总投入成本: {formatCNY(totalCost)}
              </p>
            </div>

            {/* Daily return */}
            <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
              <p className="text-sm text-slate-500 mb-1">今日收益(估算)</p>
              <p className={cn('text-2xl font-bold', colorFor(totalDailyReturn))}>
                {totalDailyReturn > 0 ? '+' : ''}
                {formatCNY(totalDailyReturn)}
              </p>
              <p className={cn('text-xs mt-2', colorFor(dailyReturnRate))}>
                今日收益率: {formatPercent(dailyReturnRate)}
              </p>
            </div>

            {/* Cumulative return */}
            <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
              <p className="text-sm text-slate-500 mb-1">累计收益</p>
              <p className={cn('text-2xl font-bold', colorFor(totalReturn))}>
                {totalReturn > 0 ? '+' : ''}
                {formatCNY(totalReturn)}
              </p>
              <p className={cn('text-xs mt-2', colorFor(totalReturnRate))}>
                累计收益率: {formatPercent(totalReturnRate)}
              </p>
            </div>

            {/* Fund count */}
            <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
              <div className="flex items-center gap-2 text-slate-500 text-sm mb-1">
                <PieChartIcon className="h-4 w-4" />
                自选基金数量
              </div>
              <p className="text-2xl font-bold text-slate-900">{fundCount}</p>
              {bestFund && (
                <p className="text-xs text-slate-400 mt-2 truncate">
                  表现最好: {bestFund.name || bestFund.code}{' '}
                  <span className={colorFor(parseFloat(bestFund.return_rate))}>
                    {formatPercent(parseFloat(bestFund.return_rate))}
                  </span>
                </p>
              )}
            </div>
          </div>

          {/* ---- Portfolio trend (placeholder) ---- */}
          {items.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
              <div className="flex items-center gap-2 mb-4">
                <TrendingUp className="h-5 w-5 text-slate-700" />
                <h2 className="text-lg font-semibold text-slate-800">组合资产走势</h2>
              </div>
              <div className="flex items-center justify-center py-12 text-slate-400 text-sm">
                暂无历史组合数据，待后端支持后展示走势图
              </div>
            </div>
          )}

          {/* ---- Holdings table + pie ---- */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            {/* Table: 2/3 */}
            <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-100">
                <h2 className="text-lg font-semibold text-slate-800">持仓明细</h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-slate-50 text-slate-500 text-xs uppercase">
                      <th className="px-4 py-3 text-left font-medium">基金名称</th>
                      <th className="px-4 py-3 text-right font-medium">净值/份额</th>
                      <th className="px-4 py-3 text-right font-medium">持仓金额/占比</th>
                      <th className="px-4 py-3 text-right font-medium">今日收益/涨跌</th>
                      <th className="px-4 py-3 text-right font-medium">累计收益</th>
                      <th className="px-4 py-3 text-center font-medium">操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {items.map((it) => {
                      const cv = parseFloat(it.current_value)
                      const dr = parseFloat(it.daily_return)
                      const tr = parseFloat(it.total_return)
                      const rr = it.return_rate != null ? parseFloat(it.return_rate) : null
                      const pct = totalCurrent > 0 ? (cv / totalCurrent) * 100 : 0
                      const cumRet = it.imported_cumulative_return != null
                        ? parseFloat(it.imported_cumulative_return) : null

                      return (
                        <tr key={it.code} className="hover:bg-slate-50 transition-colors">
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-1.5">
                              <Link
                                to={`/funds/${it.code}`}
                                className="text-slate-900 font-medium hover:text-blue-600"
                              >
                                {it.name || it.code}
                              </Link>
                              {it.is_imported && (
                                <span className="text-xs px-1 py-0.5 rounded bg-amber-50 text-amber-600 border border-amber-200">导入</span>
                              )}
                            </div>
                            <p className="text-xs text-slate-400">{it.code}</p>
                          </td>
                          <td className="px-4 py-3 text-right">
                            {it.nav != null ? (
                              <p className="text-slate-800">{parseFloat(it.nav).toFixed(4)}</p>
                            ) : <p className="text-slate-300">—</p>}
                            {it.shares != null ? (
                              <p className="text-xs text-slate-400">{parseFloat(it.shares).toFixed(2)} 份</p>
                            ) : <p className="text-xs text-slate-300">—</p>}
                          </td>
                          <td className="px-4 py-3 text-right">
                            <p className="text-slate-800">{formatCNY(cv)}</p>
                            <p className="text-xs text-slate-400">{pct.toFixed(1)}%</p>
                          </td>
                          <td className="px-4 py-3 text-right">
                            {it.is_imported ? (
                              <p className="text-xs text-slate-300">—</p>
                            ) : (
                              <>
                                <p className={cn('font-medium', colorFor(dr))}>
                                  {dr > 0 ? '+' : ''}{formatCNY(dr)}
                                </p>
                                <p className={cn('text-xs', colorFor(it.daily_change))}>
                                  {formatPercent(it.daily_change)}
                                </p>
                              </>
                            )}
                          </td>
                          <td className="px-4 py-3 text-right">
                            <p className={cn('font-medium', colorFor(tr))}>
                              {tr > 0 ? '+' : ''}{formatCNY(tr)}
                            </p>
                            {it.is_imported && cumRet != null ? (
                              <p className="text-xs text-slate-400">累计 {cumRet > 0 ? '+' : ''}{formatCNY(cumRet)}</p>
                            ) : rr != null ? (
                              <p className={cn('text-xs', colorFor(rr))}>{formatPercent(rr)}</p>
                            ) : null}
                          </td>
                          <td className="px-4 py-3 text-center">
                            <div className="flex items-center justify-center gap-1">
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
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Pie chart: 1/3 */}
            <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
              <h2 className="text-lg font-semibold text-slate-800 mb-4">持仓分布</h2>
              <div className="relative">
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={90}
                      dataKey="value"
                      stroke="none"
                    >
                      {pieData.map((_, idx) => (
                        <Cell
                          key={idx}
                          fill={PIE_COLORS[idx % PIE_COLORS.length]}
                        />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(value: number) => formatCNY(value)}
                    />
                  </PieChart>
                </ResponsiveContainer>
                {/* center label */}
                <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                  <p className="text-xs text-slate-400">基金数量</p>
                  <p className="text-2xl font-bold text-slate-900">{fundCount}</p>
                </div>
              </div>

              {/* legend */}
              <div className="mt-4 space-y-2">
                {items.map((it, idx) => {
                  const cv = parseFloat(it.current_value)
                  const pct = totalCurrent > 0 ? (cv / totalCurrent) * 100 : 0
                  return (
                    <div key={it.code} className="flex items-center justify-between text-sm">
                      <div className="flex items-center gap-2">
                        <span
                          className="inline-block h-3 w-3 rounded-full flex-shrink-0"
                          style={{ backgroundColor: PIE_COLORS[idx % PIE_COLORS.length] }}
                        />
                        <span className="text-slate-700 truncate max-w-[120px]">
                          {it.name || it.code}
                        </span>
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

      {/* ---- Watch-only funds (no position) ---- */}
      {watchOnly.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100">
            <h2 className="text-lg font-semibold text-slate-800">自选（未持仓）</h2>
          </div>
          <div className="divide-y divide-slate-100">
            {watchOnly.map((it) => (
              <div key={it.code} className="flex items-center justify-between px-6 py-3">
                <div>
                  <Link
                    to={`/funds/${it.code}`}
                    className="text-sm font-medium text-slate-900 hover:text-blue-600"
                  >
                    {it.name || it.code}
                  </Link>
                  <p className="text-xs text-slate-400">{it.code}</p>
                </div>
                <div className="flex items-center gap-6">
                  <div className="text-right">
                    <p className="text-xs text-slate-400">估算净值</p>
                    <p className="text-sm text-slate-800">
                      {it.gsz != null ? it.gsz.toFixed(4) : '—'}
                    </p>
                  </div>
                  <div className="text-right w-16">
                    <p className="text-xs text-slate-400">日涨跌</p>
                    {it.gszzl != null ? (
                      <p className={cn('text-sm font-medium', colorFor(it.gszzl))}>
                        {formatPercent(it.gszzl)}
                      </p>
                    ) : (
                      <p className="text-sm text-slate-300">—</p>
                    )}
                  </div>
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
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
