import { Info } from 'lucide-react'
import type { StockHolding } from '@/lib/api'

export function TopHoldings({ holdings }: { holdings: StockHolding[] }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
      <div className="flex items-center gap-2 mb-4">
        <Info className="h-5 w-5 text-slate-600" />
        <h2 className="text-lg font-semibold text-slate-800">重仓股票</h2>
      </div>
      {holdings.length === 0 ? (
        <div className="flex items-center justify-center h-[120px] text-slate-400 text-sm">
          暂无持仓数据
        </div>
      ) : (
        <div className="space-y-3">
          {holdings.map((h) => (
            <div key={h.stock_code}>
              <div className="flex items-center justify-between text-sm mb-1">
                <span className="text-slate-700 font-medium truncate mr-2">
                  {h.stock_name}
                </span>
                <span className="text-slate-500 text-xs whitespace-nowrap">
                  {h.percentage != null ? `${h.percentage.toFixed(2)}%` : '--'}
                </span>
              </div>
              <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 rounded-full transition-all"
                  style={{
                    width: `${Math.min((h.percentage ?? 0) / 15 * 100, 100)}%`,
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
