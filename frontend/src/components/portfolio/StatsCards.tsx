import { PieChart as PieChartIcon } from 'lucide-react'
import type { PortfolioSummary } from '@/lib/api'
import { cn, formatCNY, formatCNYSigned, formatPercent } from '@/lib/utils'
import { useColor } from '@/lib/color-context'

export function StatsCards({ summary }: { summary: PortfolioSummary }) {
  const { colorFor } = useColor()
  const items = summary.items
  const totalCurrent = parseFloat(summary.total_current)
  const totalCost = parseFloat(summary.total_cost)
  const totalDailyReturn = parseFloat(summary.total_daily_return)
  const totalReturn = parseFloat(summary.total_return)
  const totalReturnRate = parseFloat(summary.total_return_rate)

  const bestFund = items.length
    ? items.reduce((best, it) =>
        parseFloat(it.return_rate ?? String(Number.NEGATIVE_INFINITY)) >
        parseFloat(best.return_rate ?? String(Number.NEGATIVE_INFINITY))
          ? it
          : best,
      )
    : null

  const dailyReturnRate =
    totalCurrent - totalDailyReturn !== 0
      ? (totalDailyReturn / (totalCurrent - totalDailyReturn)) * 100
      : 0

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
      <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-xl p-6 shadow-lg text-white">
        <p className="text-sm text-slate-300 mb-1">总资产(预估)</p>
        <p className="text-2xl font-bold">{formatCNY(totalCurrent)}</p>
        <p className="text-xs text-slate-400 mt-2">
          总投入成本: {formatCNY(totalCost)}
        </p>
      </div>
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
        <p className="text-sm text-slate-500 mb-1">今日收益(估算)</p>
        <p className={cn('text-2xl font-bold', colorFor(totalDailyReturn))}>
          {formatCNYSigned(totalDailyReturn)}
        </p>
        <p className={cn('text-xs mt-2', colorFor(dailyReturnRate))}>
          今日收益率: {formatPercent(dailyReturnRate)}
        </p>
      </div>
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
        <p className="text-sm text-slate-500 mb-1">累计收益</p>
        <p className={cn('text-2xl font-bold', colorFor(totalReturn))}>
          {formatCNYSigned(totalReturn)}
        </p>
        <p className={cn('text-xs mt-2', colorFor(totalReturnRate))}>
          累计收益率: {formatPercent(totalReturnRate)}
        </p>
      </div>
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
        <div className="flex items-center gap-2 text-slate-500 text-sm mb-1">
          <PieChartIcon className="h-4 w-4" />
          自选基金数量
        </div>
        <p className="text-2xl font-bold text-slate-900">
          {summary.fund_count}
        </p>
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
  )
}
