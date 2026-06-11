import { Activity } from 'lucide-react'
import type { FundDetailData } from '@/lib/api'
import { cn, formatPercent } from '@/lib/utils'
import { useColor } from '@/lib/color-context'

export function StageReturns({ detail }: { detail: FundDetailData }) {
  const { colorFor } = useColor()
  const stageReturns = [
    { label: '近1月', value: detail.one_month_return },
    { label: '近3月', value: detail.three_month_return },
    { label: '近6月', value: detail.six_month_return },
    { label: '近1年', value: detail.one_year_return },
  ]

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
      <div className="flex items-center gap-2 mb-4">
        <Activity className="h-5 w-5 text-slate-600" />
        <h2 className="text-lg font-semibold text-slate-800">阶段涨幅</h2>
      </div>
      <div className="grid grid-cols-4 gap-4">
        {stageReturns.map((item) => (
          <div key={item.label} className="text-center p-3 bg-slate-50 rounded-lg">
            <p className="text-xs text-slate-400 mb-1">{item.label}</p>
            {item.value != null ? (
              <p className={cn('text-lg font-bold', colorFor(item.value))}>
                {formatPercent(item.value)}
              </p>
            ) : (
              <p className="text-lg font-bold text-slate-300">--</p>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
