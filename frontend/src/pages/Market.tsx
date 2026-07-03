import { BarChart3, Globe, RefreshCw, AlertCircle } from 'lucide-react'
import { useMarketIndices } from '@/lib/queries'
import { cn, formatNum2 } from '@/lib/utils'
import { useColor } from '@/lib/color-context'
import type { MarketIndex } from '@/lib/api'

/* ---------- index card ---------- */
function IndexCard({ data }: { data: MarketIndex }) {
  const { colorFor } = useColor()
  const sign = data.change >= 0 ? '+' : ''

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-slate-600">{data.name}</span>
        <span className="text-xs text-slate-400 font-mono">{data.code}</span>
      </div>
      <div className="text-2xl font-bold text-slate-900 tabular-nums">
        {formatNum2(data.value)}
      </div>
      <div className={cn('flex items-center gap-3 text-sm font-medium tabular-nums', colorFor(data.change_percent))}>
        <span>{sign}{data.change.toFixed(2)}</span>
        <span>{sign}{data.change_percent.toFixed(2)}%</span>
      </div>
    </div>
  )
}

/* ---------- skeleton card ---------- */
function SkeletonCard() {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 flex flex-col gap-3 animate-pulse">
      <div className="flex justify-between">
        <div className="h-4 w-20 bg-slate-100 rounded" />
        <div className="h-4 w-12 bg-slate-100 rounded" />
      </div>
      <div className="h-8 w-32 bg-slate-100 rounded" />
      <div className="h-4 w-24 bg-slate-100 rounded" />
    </div>
  )
}

/* ---------- main page ---------- */
export function Market() {
  const { data, isLoading: loading, isFetching, error: queryError, refetch, dataUpdatedAt } = useMarketIndices()

  const refreshing = isFetching && !loading
  const error = queryError ? (queryError instanceof Error ? queryError.message : '获取行情数据失败') : null
  const updatedAt = dataUpdatedAt ? new Date(dataUpdatedAt) : null

  const items = data ?? []
  const domestic = items.filter((i) => i.region === 'domestic')
  const international = items.filter((i) => i.region === 'international')

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <BarChart3 className="h-6 w-6 text-blue-600" />
            行情数据
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            全球主要市场指数行情 · 数据来源：新浪财经
          </p>
        </div>
        <div className="flex items-center gap-3">
          {updatedAt && (
            <span className="text-xs text-slate-400">
              更新于 {updatedAt.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </span>
          )}
          <button
            onClick={() => refetch()}
            disabled={refreshing}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={cn('h-4 w-4', refreshing && 'animate-spin')} />
            刷新
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 px-4 py-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-600">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Domestic */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-slate-800 flex items-center gap-2">
          <span className="inline-block w-1 h-5 bg-blue-600 rounded-full" />
          国内指数
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {loading
            ? Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)
            : domestic.map((idx) => <IndexCard key={idx.code} data={idx} />)}
        </div>
      </section>

      {/* International */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-slate-800 flex items-center gap-2">
          <Globe className="h-5 w-5 text-blue-600" />
          海外指数
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {loading
            ? Array.from({ length: 5 }).map((_, i) => <SkeletonCard key={i} />)
            : international.map((idx) => <IndexCard key={idx.code} data={idx} />)}
        </div>
      </section>

      <p className="text-xs text-slate-400 text-center pt-4">
        数据来源：新浪财经 · 海外市场非交易时段显示最近收盘价
      </p>
    </div>
  )
}
