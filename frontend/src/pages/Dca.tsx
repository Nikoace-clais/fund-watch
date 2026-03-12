import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { TrendingUp } from 'lucide-react'
import { fetchDcaPlans, fetchAllDcaStats, type DcaPlan, type DcaStats } from '@/lib/api'
import { cn, formatCNY, formatPercent } from '@/lib/utils'
import { useColor } from '@/lib/color-context'

export function Dca() {
  const { colorFor } = useColor()
  const [plans, setPlans] = useState<DcaPlan[]>([])
  const [statsMap, setStatsMap] = useState<Map<number, DcaStats>>(new Map())
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.allSettled([fetchDcaPlans(), fetchAllDcaStats()])
      .then(([plansRes, statsRes]) => {
        if (plansRes.status === 'fulfilled') setPlans(plansRes.value.items)
        if (statsRes.status === 'fulfilled') {
          const m = new Map<number, DcaStats>()
          statsRes.value.items.forEach((s) => m.set(s.plan_id, s))
          setStatsMap(m)
        }
      })
      .finally(() => setLoading(false))
  }, [])

  const allStats = [...statsMap.values()]
  const totalInvested = allStats.reduce((s, r) => s + parseFloat(r.total_invested), 0)
  const totalValue = allStats.reduce((s, r) => s + parseFloat(r.current_value), 0)
  const totalReturn = totalValue - totalInvested
  const totalReturnRate = totalInvested > 0 ? (totalReturn / totalInvested) * 100 : 0

  const freqLabel = (f: string) =>
    ({ daily:'每日', weekly:'每周', biweekly:'每两周', monthly:'每月' }[f] ?? f)

  if (loading) {
    return <div className="flex items-center justify-center py-32 text-slate-400">加载中...</div>
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">定投分析</h1>
        <p className="text-sm text-slate-500 mt-1">基于交易记录的定投绩效统计</p>
      </div>

      {/* 汇总卡片 */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-xl p-5 text-white">
          <p className="text-sm text-slate-300 mb-1">总投入</p>
          <p className="text-2xl font-bold">{formatCNY(totalInvested)}</p>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <p className="text-sm text-slate-500 mb-1">当前市值</p>
          <p className="text-2xl font-bold text-slate-900">{formatCNY(totalValue)}</p>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <p className="text-sm text-slate-500 mb-1">累计收益</p>
          <p className={cn('text-2xl font-bold', colorFor(totalReturn))}>
            {totalReturn >= 0 ? '+' : ''}{formatCNY(totalReturn)}
          </p>
          <p className={cn('text-xs mt-1', colorFor(totalReturnRate))}>
            {formatPercent(totalReturnRate)}
          </p>
        </div>
      </div>

      {/* 计划列表 */}
      {plans.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <TrendingUp className="h-10 w-10 text-slate-300 mb-4" />
          <p className="text-slate-400">暂无定投计划</p>
          <p className="text-sm text-slate-300 mt-1">在基金详情页新建定投计划后将显示在此</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100">
            <h2 className="text-lg font-semibold text-slate-800">全部计划</h2>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-xs text-slate-400 uppercase">
                <th className="text-left px-6 py-3 font-medium">基金</th>
                <th className="text-left px-4 py-3 font-medium">计划</th>
                <th className="text-right px-4 py-3 font-medium">每期金额</th>
                <th className="text-center px-4 py-3 font-medium">进度</th>
                <th className="text-right px-4 py-3 font-medium">总投入</th>
                <th className="text-right px-4 py-3 font-medium">均价</th>
                <th className="text-right px-6 py-3 font-medium">收益率</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {plans.map((plan) => {
                const s = statsMap.get(plan.id)
                const rr = s ? parseFloat(s.return_rate) : 0
                return (
                  <tr key={plan.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-6 py-3">
                      <Link
                        to={`/funds/${plan.code}`}
                        className="font-medium text-slate-900 hover:text-blue-600"
                      >
                        {plan.code}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-slate-500">
                      {plan.name || freqLabel(plan.frequency)}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-700">
                      ¥{parseFloat(plan.amount).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-center text-slate-500">
                      {s ? `${s.success_count}/${s.total_periods}` : '—'}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-700">
                      {s ? formatCNY(parseFloat(s.total_invested)) : '—'}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-700 font-mono">
                      {s ? parseFloat(s.avg_cost).toFixed(4) : '—'}
                    </td>
                    <td className={cn('px-6 py-3 text-right font-semibold', colorFor(rr))}>
                      {s ? `${rr >= 0 ? '+' : ''}${s.return_rate}%` : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
