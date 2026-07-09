import { useMemo, useState } from 'react'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceDot,
} from 'recharts'
import { TrendingUp } from 'lucide-react'
import type { NavPoint, Transaction } from '@/lib/api'
import { cn } from '@/lib/utils'

const RANGE_OPTIONS = [
  { label: '1月', days: 21 },
  { label: '3月', days: 63 },
  { label: '半年', days: 126 },
  { label: '1年', days: 252 },
  { label: '全部', days: 0 },
] as const

function formatDate(dateStr: string) {
  const d = new Date(dateStr)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

export function NavChart({
  history,
  transactions,
}: {
  history: NavPoint[]
  transactions: Transaction[]
}) {
  const [range, setRange] = useState<number>(63) // default 3M

  const filteredHistory = useMemo(() => {
    if (range === 0) return history
    return history.slice(-range)
  }, [history, range])

  const tradeMap = useMemo(() => {
    const map = new Map<string, Transaction[]>()
    for (const tx of transactions) {
      const list = map.get(tx.trade_date) ?? []
      list.push(tx)
      map.set(tx.trade_date, list)
    }
    return map
  }, [transactions])

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-slate-600" />
          <h2 className="text-lg font-semibold text-slate-800">净值走势</h2>
        </div>
        {/* range selector */}
        <div className="flex bg-slate-100 rounded-lg p-1">
          {RANGE_OPTIONS.map((opt) => (
            <button
              key={opt.label}
              onClick={() => setRange(opt.days)}
              className={cn(
                'px-3 py-1 text-xs font-medium rounded-md transition-all',
                range === opt.days
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700',
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {filteredHistory.length === 0 ? (
        <div className="flex items-center justify-center h-[300px] text-slate-400">
          暂无净值数据
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart
            data={filteredHistory}
            margin={{ top: 5, right: 10, left: 10, bottom: 5 }}
          >
            <defs>
              <linearGradient id="navGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis
              dataKey="date"
              tickFormatter={formatDate}
              tick={{ fontSize: 11, fill: '#94a3b8' }}
              axisLine={{ stroke: '#e2e8f0' }}
              tickLine={false}
            />
            <YAxis
              orientation="right"
              tickFormatter={(v: number) => v.toFixed(4)}
              tick={{ fontSize: 11, fill: '#94a3b8' }}
              axisLine={false}
              tickLine={false}
              domain={['auto', 'auto']}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#0f172a',
                border: 'none',
                borderRadius: '8px',
                color: '#fff',
                fontSize: 13,
              }}
              labelStyle={{ color: '#94a3b8' }}
              formatter={(value: number) => [value.toFixed(4), '净值']}
              labelFormatter={(label: string) => `日期: ${label}`}
            />
            <Area
              type="monotone"
              dataKey="nav"
              stroke="#3b82f6"
              strokeWidth={2}
              fill="url(#navGradient)"
              dot={false}
              activeDot={{
                r: 4,
                strokeWidth: 2,
                fill: '#fff',
                stroke: '#3b82f6',
              }}
            />
            {filteredHistory.flatMap((point) => {
              const txs = tradeMap.get(point.date)
              if (!txs || txs.length === 0) return []
              // 同日有买入优先显示买入色
              const hasBuy = txs.some((t) => t.direction === 'buy')
              const color = hasBuy ? '#ef4444' : '#10b981'
              return [
                <ReferenceDot
                  key={point.date}
                  x={point.date}
                  y={point.nav}
                  r={5}
                  fill={color}
                  stroke="#fff"
                  strokeWidth={2}
                />,
              ]
            })}
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
