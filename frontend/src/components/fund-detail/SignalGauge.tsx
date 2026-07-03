import { useMemo } from 'react'
import type { NavPoint } from '@/lib/api'
import { computeSignals, signalVerdict } from '@/lib/fund-metrics'
import { useColor } from '@/lib/color-context'

// ── SVG gauge constants ───────────────────────────────────────────────────────

const CX = 100, CY = 105, R = 80, SW = 14

function toRad(deg: number) { return (deg * Math.PI) / 180 }

// Stroke-based arc on the centerline radius R.
// sweep=1 → CW in SVG y-down = traces the UPPER semicircle.
// Adjacent segments share the same endpoint coords → butt linecap joints are seamless.
function arcPath(a1Deg: number, a2Deg: number) {
  const pt = (a: number) =>
    `${(CX + R * Math.cos(toRad(a))).toFixed(1)} ${(CY - R * Math.sin(toRad(a))).toFixed(1)}`
  return `M ${pt(a1Deg)} A ${R} ${R} 0 0 1 ${pt(a2Deg)}`
}

// ── Sub-components ────────────────────────────────────────────────────────────

function ScoreBar({
  label, hint, score, color,
}: { label: string; hint: string; score: number; color: string }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-14 shrink-0 text-slate-500">{label}</span>
      <div className="flex-1 bg-slate-100 rounded-full h-1.5 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${score}%`, backgroundColor: color }}
        />
      </div>
      <span className="w-20 text-right text-slate-500 shrink-0">{hint}</span>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export function SignalGauge({ history }: { history: NavPoint[] }) {
  const result = useMemo(() => {
    const s = computeSignals(history)
    return s ? { s, v: signalVerdict(s) } : null
  }, [history])
  const { scheme } = useColor()
  // buy-side / sell-side stroke colors (red = up in A-share convention)
  const bull = { stroke: scheme === 'red-up' ? '#ef4444' : '#22c55e' }
  const bear = { stroke: scheme === 'red-up' ? '#22c55e' : '#ef4444' }

  if (!result) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-slate-600">🎯</span>
          <h2 className="text-lg font-semibold text-slate-800">买卖信号</h2>
        </div>
        <p className="text-sm text-slate-400">数据不足，无法计算买卖信号</p>
      </div>
    )
  }

  const { s, v } = result
  const needleColor =
    v.level >= 3 ? bull.stroke
    : v.level <= 1 ? bear.stroke
    : '#64748b'

  // composite 0 → needle at 180° (far left = sell), 100 → 0° (far right = buy)
  const needleAngleDeg = 180 - (v.composite / 100) * 180
  const θ = toRad(needleAngleDeg)
  const cosθ = Math.cos(θ), sinθ = Math.sin(θ)
  const L = 66, back = 8, hw = 3.5 // needle: length, tail, half-width at hub

  // needle polygon: tip → base-right → tail → base-left
  const needlePoints = [
    `${(CX + L * cosθ).toFixed(1)},${(CY - L * sinθ).toFixed(1)}`,
    `${(CX - hw * sinθ).toFixed(1)},${(CY - hw * cosθ).toFixed(1)}`,
    `${(CX - back * cosθ).toFixed(1)},${(CY + back * sinθ).toFixed(1)}`,
    `${(CX + hw * sinθ).toFixed(1)},${(CY + hw * cosθ).toFixed(1)}`,
  ].join(' ')

  const barColor = (score: number) =>
    score >= 55 ? bull.stroke : score <= 45 ? bear.stroke : '#94a3b8'

  const trendSign = s.trendRatio >= 0 ? '+' : ''
  const trendHint = `MA20/60 ${trendSign}${(s.trendRatio * 100).toFixed(1)}%`

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-4">
      <div className="flex items-center gap-2">
        <span className="text-slate-600">🎯</span>
        <h2 className="text-lg font-semibold text-slate-800">买卖信号</h2>
      </div>

      <div className="flex flex-col items-center gap-1">
        <svg viewBox="0 5 200 115" className="w-full max-w-[230px]">
          {/* Background track — butt ends, covered by colored segments */}
          <path d={arcPath(180, 0)} fill="none" stroke="#e2e8f0" strokeWidth={SW} strokeLinecap="butt" />
          {/* 5 colored segments — butt linecap → adjacent endpoints share exact coords → no gaps, no concave seams */}
          <path d={arcPath(180, 144)} fill="none" stroke={bear.stroke} strokeWidth={SW} strokeLinecap="butt" />
          <path d={arcPath(144, 108)} fill="none" stroke={bear.stroke} strokeWidth={SW} strokeLinecap="butt" strokeOpacity={0.45} />
          <path d={arcPath(108,  72)} fill="none" stroke="#94a3b8"    strokeWidth={SW} strokeLinecap="butt" />
          <path d={arcPath( 72,  36)} fill="none" stroke={bull.stroke} strokeWidth={SW} strokeLinecap="butt" strokeOpacity={0.45} />
          <path d={arcPath( 36,   0)} fill="none" stroke={bull.stroke} strokeWidth={SW} strokeLinecap="butt" />
          {/* Rounded caps at the two arc endpoints */}
          <circle cx={CX - R} cy={CY} r={SW / 2} fill={bear.stroke} />
          <circle cx={CX + R} cy={CY} r={SW / 2} fill={bull.stroke} />
          {/* Needle */}
          <polygon points={needlePoints} fill={needleColor} />
          {/* Hub: white ring + colored center */}
          <circle cx={CX} cy={CY} r={9}   fill="white" />
          <circle cx={CX} cy={CY} r={6}   fill={needleColor} />
          <circle cx={CX} cy={CY} r={2.5} fill="white" />
          {/* Endpoint labels */}
          <text x={CX - R - 2} y={CY + 16} fontSize="9" fill={bear.stroke}
            fontWeight="700" textAnchor="middle">卖</text>
          <text x={CX + R + 2} y={CY + 16} fontSize="9" fill={bull.stroke}
            fontWeight="700" textAnchor="middle">买</text>
        </svg>

        <p className="text-2xl font-bold leading-none" style={{ color: needleColor }}>
          {v.label}
        </p>
        <p className="text-[10px] text-slate-400 mt-0.5">{v.reason}</p>
      </div>

      <div className="space-y-2 pt-2 border-t border-slate-100">
        <ScoreBar
          label="质量"
          hint={s.sharpe != null ? `夏普 ${s.sharpe.toFixed(2)}` : '--'}
          score={s.quality ?? 0}
          color={barColor(s.quality ?? 0)}
        />
        <ScoreBar
          label="估值"
          hint={`${s.percentile.toFixed(0)}% 分位`}
          score={s.valuation}
          color={barColor(s.valuation)}
        />
        <ScoreBar
          label="趋势"
          hint={trendHint}
          score={s.trend}
          color={barColor(s.trend)}
        />
      </div>

      <p className="text-[10px] text-slate-300 text-center pt-1">估算参考，非投资建议</p>
    </div>
  )
}
