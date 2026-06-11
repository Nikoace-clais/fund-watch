import { useState } from 'react'
import { TrendingUp } from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, ReferenceLine, Tooltip, ResponsiveContainer,
} from 'recharts'
import { usePortfolioHistory } from '@/lib/queries'
import { cn, formatCNY } from '@/lib/utils'

const RANGES = [21, 63, 126, 252] as const
type TrendRange = (typeof RANGES)[number]

export function TrendChart({ totalCost }: { totalCost: number }) {
  const [range, setRange] = useState<TrendRange>(63)
  const { data: history = [], isLoading } = usePortfolioHistory(range)

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-slate-700" />
          <h2 className="text-lg font-semibold text-slate-800">组合资产走势</h2>
        </div>
        <div className="flex items-center gap-1">
          {RANGES.map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={cn(
                'px-3 py-1 rounded-md text-xs font-medium transition-colors',
                range === r
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-500 hover:text-slate-700 hover:bg-slate-100',
              )}
            >
              {r === 21 ? '1月' : r === 63 ? '3月' : r === 126 ? '6月' : '1年'}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="h-52 flex items-center justify-center text-slate-400 text-sm">加载中...</div>
      ) : history.length < 2 ? (
        <div className="h-52 flex items-center justify-center text-slate-400 text-sm">
          暂无足够的历史数据，持仓交易记录后将自动展示
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={history} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
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
  )
}
