import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, TrendingUp } from 'lucide-react'
import { deleteDcaPlan, type DcaPlan } from '@/lib/api'
import { useDcaPlanRecords, useDcaPlans, useDcaPlanStats } from '@/lib/queries'
import { DcaPlanModal } from '@/components/DcaPlanModal'
import { cn } from '@/lib/utils'
import { useColor } from '@/lib/color-context'

const FREQ_LABELS: Record<DcaPlan['frequency'], string> = {
  daily: '每日',
  weekly: '每周',
  biweekly: '每两周',
  monthly: '每月',
}

function PlanRow({
  plan,
  expanded,
  onToggle,
  onDelete,
}: {
  plan: DcaPlan
  expanded: boolean
  onToggle: () => void
  onDelete: () => void
}) {
  const { colorFor } = useColor()
  const { data: stats } = useDcaPlanStats(plan.id)
  const { data: records = [] } = useDcaPlanRecords(plan.id, expanded)
  const freqLabel = FREQ_LABELS[plan.frequency]

  return (
    <div className="border border-slate-100 rounded-lg overflow-hidden">
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-slate-50 transition-colors"
        onClick={onToggle}
      >
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-slate-800 truncate">
            {plan.name || `${freqLabel}定投`}
          </p>
          <p className="text-xs text-slate-400 mt-0.5">
            {freqLabel} · ¥{parseFloat(plan.amount).toLocaleString()} · 起 {plan.start_date}
          </p>
        </div>
        {stats && (
          <div className="text-right shrink-0">
            <p className="text-xs text-slate-400">{stats.success_count}/{stats.total_periods} 期成功</p>
            <p className={cn('text-sm font-semibold', colorFor(parseFloat(stats.return_rate)))}>
              {parseFloat(stats.return_rate) >= 0 ? '+' : ''}{stats.return_rate}%
            </p>
          </div>
        )}
        <button
          onClick={(e) => {
            e.stopPropagation()
            onDelete()
          }}
          className="p-1 rounded text-slate-300 hover:text-red-500 hover:bg-red-50 transition-colors"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>

      {expanded && (
        <div className="border-t border-slate-100 bg-slate-50 px-4 py-3">
          {records.length === 0 ? (
            <p className="text-xs text-slate-400 text-center py-2">暂无执行记录</p>
          ) : (
            <table className="w-full text-xs">
              <thead>
                <tr className="text-slate-400 border-b border-slate-200">
                  <th className="text-left pb-1.5 font-medium">预定日期</th>
                  <th className="text-center pb-1.5 font-medium">状态</th>
                  <th className="text-right pb-1.5 font-medium">净值</th>
                  <th className="text-right pb-1.5 font-medium">份额</th>
                  <th className="text-right pb-1.5 font-medium">金额</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {records.map((r) => (
                  <tr key={r.id} className="hover:bg-white transition-colors">
                    <td className="py-1.5 text-slate-600">{r.scheduled_date}</td>
                    <td className="py-1.5 text-center">
                      <span className={cn(
                        'inline-block px-1.5 py-0.5 rounded text-xs font-medium',
                        r.status === 'success'
                          ? 'bg-green-50 text-green-600'
                          : 'bg-slate-100 text-slate-400',
                      )}>
                        {r.status === 'success' ? '成功' : '失败'}
                      </span>
                    </td>
                    <td className="py-1.5 text-right text-slate-600">
                      {r.nav ? parseFloat(r.nav).toFixed(4) : '—'}
                    </td>
                    <td className="py-1.5 text-right text-slate-600">
                      {r.shares ? parseFloat(r.shares).toFixed(2) : '—'}
                    </td>
                    <td className="py-1.5 text-right text-slate-600">
                      {r.tx_amount ? `¥${parseFloat(r.tx_amount).toFixed(2)}` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}

export function DcaSection({ code, name }: { code: string; name?: string }) {
  const qc = useQueryClient()
  const { data: plans = [] } = useDcaPlans(code)
  const [expandedPlan, setExpandedPlan] = useState<number | null>(null)
  const [showModal, setShowModal] = useState(false)

  const invalidateDca = () => qc.invalidateQueries({ queryKey: ['dca'] })

  const handleDeletePlan = (planId: number) => {
    if (!confirm('确认删除此定投计划？')) return
    deleteDcaPlan(planId).then(invalidateDca)
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
      <div className="flex items-center gap-2 mb-4">
        <TrendingUp className="h-5 w-5 text-slate-600" />
        <h2 className="text-lg font-semibold text-slate-800">定投计划</h2>
        <span className="text-xs text-slate-400">{plans.length} 个</span>
        <button
          onClick={() => setShowModal(true)}
          className="ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-500 text-white text-sm hover:bg-blue-600 transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />
          新建计划
        </button>
      </div>

      {plans.length === 0 ? (
        <div className="flex items-center justify-center h-20 text-slate-400 text-sm">
          暂无定投计划
        </div>
      ) : (
        <div className="space-y-3">
          {plans.map((plan) => (
            <PlanRow
              key={plan.id}
              plan={plan}
              expanded={expandedPlan === plan.id}
              onToggle={() => setExpandedPlan(expandedPlan === plan.id ? null : plan.id)}
              onDelete={() => handleDeletePlan(plan.id)}
            />
          ))}
        </div>
      )}

      <DcaPlanModal
        open={showModal}
        code={code}
        name={name}
        onClose={() => setShowModal(false)}
        onSaved={invalidateDca}
      />
    </div>
  )
}
