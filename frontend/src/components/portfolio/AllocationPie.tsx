import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'
import type { PortfolioItem } from '@/lib/api'
import { CHART_COLORS as PIE_COLORS, formatCNY } from '@/lib/utils'

export function AllocationPie({
  items,
  totalCurrent,
  fundCount,
}: {
  items: PortfolioItem[]
  totalCurrent: number
  fundCount: number
}) {
  // skip rows whose valuation is unavailable (estimate_error) — they have no
  // meaningful share of the pie
  const valued = items.filter((it) => it.current_value != null)
  const pieData = valued.map((it) => ({
    name: it.name || it.code,
    value: parseFloat(it.current_value!),
  }))

  return (
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
                <Cell key={idx} fill={PIE_COLORS[idx % PIE_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              formatter={(value: number) => formatCNY(value)}
              wrapperStyle={{ zIndex: 10 }}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <p className="text-xs text-slate-400">基金数量</p>
          <p className="text-2xl font-bold text-slate-900">{fundCount}</p>
        </div>
      </div>
      <div className="mt-4 space-y-2 max-h-48 overflow-y-auto">
        {valued.map((it, idx) => {
          const cv = parseFloat(it.current_value!)
          const pct = totalCurrent > 0 ? (cv / totalCurrent) * 100 : 0
          return (
            <div
              key={it.code}
              className="flex items-center justify-between text-sm"
            >
              <div className="flex items-center gap-2">
                <span
                  className="inline-block h-3 w-3 rounded-full shrink-0"
                  style={{
                    backgroundColor: PIE_COLORS[idx % PIE_COLORS.length],
                  }}
                />
                <span className="text-slate-700 truncate max-w-[120px]">
                  {it.name || it.code}
                </span>
              </div>
              <span className="text-slate-500 font-medium">
                {pct.toFixed(1)}%
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
