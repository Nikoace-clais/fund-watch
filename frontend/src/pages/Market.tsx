import { useMemo } from 'react'
import { AreaChart, Area, ResponsiveContainer } from 'recharts'
import { BarChart3, Globe } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useColor } from '@/lib/color-context'

/* ==========================================================================
   Market Index Page — 行情数据

   TODO: Replace mock data with real Sina Finance API once a backend proxy is
   available. The Sina API has CORS restrictions so browser-direct calls won't
   work. Planned proxy endpoint: GET /api/market/indices

   Sina API format (domestic):
     https://hq.sinajs.cn/list=s_sh000001,s_sz399001,s_sz399006,s_sh000300,s_sh000016,s_sz399673
   Sina API format (international):
     https://hq.sinajs.cn/list=int_dji,int_nasdaq,int_sp500,int_hangseng,int_nikkei,b_TWSE,b_KOSPI

   Response fields: name, current price, change amount, change%, volume, turnover
   ========================================================================== */

/* ---------- types ---------- */
type IndexData = {
  code: string
  name: string
  value: number
  change: number
  changePercent: number
  sparkline: { v: number }[]
}

/* ---------- sparkline data generator ---------- */
function generateSparkline(current: number, changePercent: number, points = 20): { v: number }[] {
  const direction = changePercent >= 0 ? 1 : -1
  const range = current * Math.abs(changePercent) * 0.015
  const data: { v: number }[] = []
  let v = current - current * (changePercent / 100)

  for (let i = 0; i < points; i++) {
    const progress = i / (points - 1)
    const trend = direction * range * progress
    const noise = (Math.random() - 0.5) * range * 0.6
    v = current - current * (changePercent / 100) + trend + noise
    data.push({ v: parseFloat(v.toFixed(2)) })
  }
  data[points - 1] = { v: current }
  return data
}

/* ---------- mock data ---------- */
const DOMESTIC_INDICES: IndexData[] = [
  { code: '000001', name: '上证指数', value: 3286.53, change: 20.12, changePercent: 0.42, sparkline: [] },
  { code: '399001', name: '深证成指', value: 10512.78, change: -18.94, changePercent: -0.18, sparkline: [] },
  { code: '399006', name: '创业板指', value: 2134.61, change: 22.24, changePercent: 1.05, sparkline: [] },
  { code: '000300', name: '沪深300', value: 3865.42, change: 15.38, changePercent: 0.40, sparkline: [] },
  { code: '000016', name: '上证50', value: 2714.36, change: -5.67, changePercent: -0.21, sparkline: [] },
  { code: '000905', name: '中证500', value: 5823.15, change: 45.72, changePercent: 0.79, sparkline: [] },
].map((d) => ({ ...d, sparkline: generateSparkline(d.value, d.changePercent) }))

const INTERNATIONAL_INDICES: IndexData[] = [
  { code: 'DJI', name: '道琼斯工业', value: 43287.65, change: 152.34, changePercent: 0.35, sparkline: [] },
  { code: 'NASDAQ', name: '纳斯达克', value: 18632.41, change: -87.56, changePercent: -0.47, sparkline: [] },
  { code: 'SPX', name: '标普500', value: 5912.78, change: 23.45, changePercent: 0.40, sparkline: [] },
  { code: 'HSI', name: '恒生指数', value: 22145.32, change: -312.18, changePercent: -1.39, sparkline: [] },
  { code: 'N225', name: '日经225', value: 38456.12, change: 285.63, changePercent: 0.75, sparkline: [] },
  { code: 'FTSE', name: '富时100', value: 8234.56, change: -12.34, changePercent: -0.15, sparkline: [] },
].map((d) => ({ ...d, sparkline: generateSparkline(d.value, d.changePercent) }))

/* ---------- index card component ---------- */
function IndexCard({ data }: { data: IndexData }) {
  const { colorFor, chartColorFor } = useColor()
  const colors = chartColorFor(data.changePercent)
  const sign = data.change >= 0 ? '+' : ''

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 flex flex-col gap-3">
      {/* Top: name + code */}
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-slate-600">{data.name}</span>
        <span className="text-xs text-slate-400 font-mono">{data.code}</span>
      </div>

      {/* Current value */}
      <div className="text-2xl font-bold text-slate-900 tabular-nums">
        {data.value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </div>

      {/* Change row */}
      <div className={cn('flex items-center gap-3 text-sm font-medium tabular-nums', colorFor(data.changePercent))}>
        <span>{sign}{data.change.toFixed(2)}</span>
        <span>{sign}{data.changePercent.toFixed(2)}%</span>
      </div>

      {/* Sparkline */}
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

/* ---------- main page component ---------- */
export function Market() {
  const domestic = useMemo(() => DOMESTIC_INDICES, [])
  const international = useMemo(() => INTERNATIONAL_INDICES, [])

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <BarChart3 className="h-6 w-6 text-blue-600" />
          行情数据
        </h1>
        <p className="text-sm text-slate-500 mt-1">全球主要市场指数实时行情</p>
      </div>

      {/* Domestic indices */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-slate-800 flex items-center gap-2">
          <span className="inline-block w-1 h-5 bg-blue-600 rounded-full" />
          国内指数
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {domestic.map((idx) => (
            <IndexCard key={idx.code} data={idx} />
          ))}
        </div>
      </section>

      {/* International indices */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-slate-800 flex items-center gap-2">
          <Globe className="h-5 w-5 text-blue-600" />
          海外指数
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {international.map((idx) => (
            <IndexCard key={idx.code} data={idx} />
          ))}
        </div>
      </section>

      {/* Footer note */}
      <p className="text-xs text-slate-400 text-center pt-4">
        数据为模拟展示，实时行情接入开发中 · 数据来源计划：新浪财经
      </p>
    </div>
  )
}
