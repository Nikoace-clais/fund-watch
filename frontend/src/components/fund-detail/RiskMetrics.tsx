import type { NavPoint, FundDetailData } from '@/lib/api'
import { computeRiskMetrics } from '@/lib/fund-metrics'

// ── Emoji grading ─────────────────────────────────────────────────────────────

function returnGrade(v: number) {
  if (v >= 20) return '🚀'
  if (v >= 5) return '📈'
  if (v >= 0) return '😐'
  return '📉'
}

function volGrade(v: number) {
  if (v < 10) return '🧊'
  if (v < 20) return '💧'
  if (v < 30) return '🌊'
  return '🌪️'
}

function ddGrade(v: number) {
  if (v < 10) return '🛡️'
  if (v < 20) return '💚'
  if (v < 30) return '🟡'
  return '🔴'
}

function sharpeGrade(v: number) {
  if (v >= 1.5) return '🏆'
  if (v >= 1.0) return '⭐'
  if (v >= 0.5) return '👍'
  if (v >= 0) return '😐'
  return '⚠️'
}

// ── Component ─────────────────────────────────────────────────────────────────

type Props = {
  history: NavPoint[]
  detail: FundDetailData
}

function MetricCard({
  label,
  value,
  grade,
  hint,
}: {
  label: string
  value: string
  grade: string
  hint?: string
}) {
  return (
    <div className="text-center p-3 bg-slate-50 rounded-lg" title={hint}>
      <p className="text-xs text-slate-400 mb-1">{label}</p>
      <p className="text-base font-bold text-slate-800">{value}</p>
      <p className="text-lg mt-0.5">{grade}</p>
    </div>
  )
}

function PowerBar({ label, score }: { label: string; score: number }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-16 text-slate-500 shrink-0">{label}</span>
      <div className="flex-1 bg-slate-100 rounded-full h-1.5 overflow-hidden">
        <div
          className="h-full bg-blue-400 rounded-full"
          style={{ width: `${score}%` }}
        />
      </div>
      <span className="w-8 text-right text-slate-600 font-medium">
        {score.toFixed(0)}
      </span>
    </div>
  )
}

export function RiskMetrics({ history, detail }: Props) {
  const metrics = computeRiskMetrics(history)

  const fmt = (v: number | null, suffix = '%') =>
    v != null ? `${v >= 0 ? '+' : ''}${v.toFixed(2)}${suffix}` : '--'

  const fmtSharpe = (v: number | null) => (v != null ? v.toFixed(2) : '--')

  const hasPower =
    detail.manager_power_scores &&
    detail.manager_power_categories &&
    detail.manager_power_scores.length ===
      detail.manager_power_categories.length

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-5">
      <div className="flex items-center gap-2">
        <span className="text-slate-600">📊</span>
        <h2 className="text-lg font-semibold text-slate-800">风险指标</h2>
        <span className="text-xs text-slate-400 ml-1">（近252交易日）</span>
      </div>

      {metrics ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <MetricCard
            label="年化收益率"
            value={fmt(metrics.annualReturn)}
            grade={
              metrics.annualReturn != null
                ? returnGrade(metrics.annualReturn)
                : '–'
            }
            hint="≥20%🚀 ≥5%📈 ≥0%😐 <0%📉"
          />
          <MetricCard
            label="年化波动率"
            value={fmt(metrics.annualVol)}
            grade={volGrade(metrics.annualVol)}
            hint="<10%🧊 <20%💧 <30%🌊 ≥30%🌪️"
          />
          <MetricCard
            label="最大回撤"
            value={`-${metrics.maxDrawdown.toFixed(2)}%`}
            grade={ddGrade(metrics.maxDrawdown)}
            hint="<10%🛡️ <20%💚 <30%🟡 ≥30%🔴"
          />
          <MetricCard
            label="夏普比率"
            value={fmtSharpe(metrics.sharpe)}
            grade={metrics.sharpe != null ? sharpeGrade(metrics.sharpe) : '–'}
            hint="≥1.5🏆 ≥1.0⭐ ≥0.5👍 ≥0😐 <0⚠️"
          />
        </div>
      ) : (
        <p className="text-sm text-slate-400">数据不足，无法计算风险指标</p>
      )}

      {hasPower && (
        <div className="space-y-2 pt-1 border-t border-slate-100">
          <p className="text-xs font-medium text-slate-500">
            基金经理能力（天天基金评分）
          </p>
          {detail.manager_power_categories!.map((cat, i) => (
            <PowerBar
              key={cat}
              label={cat}
              score={detail.manager_power_scores![i]}
            />
          ))}
        </div>
      )}
    </div>
  )
}
