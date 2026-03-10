import { useEffect, useState, useCallback } from 'react'
import { AreaChart, Area, ResponsiveContainer } from 'recharts'
import { BarChart3, Globe, RefreshCw, AlertCircle } from 'lucide-react'
import { fetchMarketIndices } from '@/lib/api'
import { cn } from '@/lib/utils'
import { useColor } from '@/lib/color-context'

/* ---------- types ---------- */
type IndexItem = {
  code: string
  name: string
  value: number
  change: number
  change_percent: number
}

type IndexData = IndexItem & {
  sparkline: { v: number }[]
}

/* ---------- sparkline generator (decorative, no historical data) ---------- */
function generateSparkline(current: number, changePercent: number, points = 20): { v: number }[] {
  const direction = changePercent >= 0 ? 1 : -1
  const range = current * Math.abs(changePercent) * 0.015
  const data: { v: number }[] = []
  for (let i = 0; i < points; i++) {
    const progress = i / (points - 1)
    const trend = direction * range * progress
    const noise = (Math.random() - 0.5) * range * 0.6
    const v = current - current * (changePercent / 100) + trend + noise
    data.push({ v: parseFloat(v.toFixed(2)) })
  }
  data[points - 1] = { v: current }
  return data
}

/* ---------- domestic / overseas split ---------- */
const DOMESTIC_CODES = new Set(['000001', '399001', '399006', '399300', '000016', '000905'])

/* ---------- index card ---------- */
function IndexCard({ data }: { data: IndexData }) {
  const { colorFor, chartColorFor } = useColor()
  const colors = chartColorFor(data.change_percent)
  const sign = data.change >= 0 ? '+' : ''

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-slate-600">{data.name}</span>
        <span className="text-xs text-slate-400 font-mono">{data.code}</span>
      </div>
      <div className="text-2xl font-bold text-slate-900 tabular-nums">
        {data.value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </div>
      <div className={cn('flex items-center gap-3 text-sm font-medium tabular-nums', colorFor(data.change_percent))}>
        <span>{sign}{data.change.toFixed(2)}</span>
        <span>{sign}{data.change_percent.toFixed(2)}%</span>
      </div>
      <div className="h-12 -mx-1">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data.sparkline} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id={`grad-${data.code}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={colors.fill} stopOpacity={0.6} />
                <stop offset="100%" stopColor={colors.fill} stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <Area
              type="monotone"
              dataKey="v"
              stroke={colors.stroke}
              strokeWidth={1.5}
              fill={`url(#grad-${data.code})`}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
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
      <div className="h-12 bg-slate-50 rounded" />
    </div>
  )
}

/* ---------- main page ---------- */
export function Market() {
  const [items, setItems] = useState<IndexData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true)
    else setLoading(true)
    setError(null)
    try {
      const data = await fetchMarketIndices()
      setItems(
        data.items.map((item) => ({
          ...item,
          sparkline: generateSparkline(item.value, item.change_percent),
        }))
      )
      setUpdatedAt(new Date())
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '获取行情数据失败')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const domestic = items.filter((i) => DOMESTIC_CODES.has(i.code))
  const international = items.filter((i) => !DOMESTIC_CODES.has(i.code))

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
            全球主要市场指数行情 · 数据来源：东方财富
          </p>
        </div>
        <div className="flex items-center gap-3">
          {updatedAt && (
            <span className="text-xs text-slate-400">
              更新于 {updatedAt.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </span>
          )}
          <button
            onClick={() => load(true)}
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
        数据来源：东方财富 push2 API · 海外市场非交易时段显示最近收盘价
      </p>
    </div>
  )
}
