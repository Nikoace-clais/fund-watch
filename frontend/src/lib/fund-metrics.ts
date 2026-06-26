import type { NavPoint } from '@/lib/api'

// ponytail: all thresholds heuristic; tune from observed fund behavior
const QUALITY_FLOOR = 25   // sharpeScore < 25 fails gate (≈ sharpe 0.5)
const CHEAP        = 65    // valuation ≥ 65 → below ~35th pct = cheap
const EXPENSIVE    = 35    // valuation ≤ 35 → above ~65th pct = expensive
const TREND_EPS    = 0.005 // ±0.5% MA20/MA60 gap = neutral zone
const TREND_K      = 1000  // trendRatio × K → score offset from 50

/**
 * 风险指标计算（近 252 交易日）：年化收益、波动率、最大回撤、夏普比率。
 * 样本不足 30 个有效日收益点时返回 null。
 */
export function computeRiskMetrics(history: NavPoint[]) {
  const slice = history.slice(-252)
  const returns = slice
    .filter(p => p.dailyReturn != null)
    .map(p => p.dailyReturn! / 100)

  if (returns.length < 30) return null

  const navSlice = slice.filter(p => p.nav != null)
  const startNav = navSlice[0]?.nav
  const endNav = navSlice[navSlice.length - 1]?.nav
  const n = returns.length
  const annualReturn =
    startNav && endNav
      ? (Math.pow(endNav / startNav, 252 / n) - 1) * 100
      : null

  const mean = returns.reduce((a, b) => a + b, 0) / n
  const variance = returns.reduce((a, b) => a + (b - mean) ** 2, 0) / n
  const annualVol = Math.sqrt(variance * 252) * 100

  let peak = -Infinity
  let maxDD = 0
  for (const p of navSlice) {
    if (p.nav! > peak) peak = p.nav!
    const dd = (peak - p.nav!) / peak
    if (dd > maxDD) maxDD = dd
  }
  const maxDrawdown = maxDD * 100

  const RISK_FREE = 2
  const sharpe =
    annualReturn != null && annualVol > 0
      ? (annualReturn - RISK_FREE) / annualVol
      : null

  return { annualReturn, annualVol, maxDrawdown, sharpe }
}

const ma = (seq: number[], n: number) => {
  const s = seq.slice(-n)
  return s.reduce((a, b) => a + b, 0) / s.length
}

/**
 * 三轴买卖信号。≥30 个净值点才出信号；< 60 点时趋势视为中性（trendRatio = 0）。
 * - quality:   夏普得分 0–100（null = 数据不足，会触发「观望」）
 * - valuation: 历史分位得分 0–100（越高越便宜）
 * - trend:     MA20/MA60 偏离得分 0–100（>50 向上，<50 向下）
 */
export function computeSignals(history: NavPoint[]) {
  if (history.length < 30) return null

  const seq = history.map(p => p.accNav ?? p.nav)
  const current = seq[seq.length - 1]

  // Quality: reuse computeRiskMetrics for sharpe
  const risk = computeRiskMetrics(history)
  const sharpe = risk?.sharpe ?? null
  const quality = sharpe !== null ? Math.max(0, Math.min((sharpe / 2) * 100, 100)) : null

  // Valuation: historical percentile (low percentile = cheap = high score)
  const below = seq.filter(v => v <= current).length
  const percentile = (below / seq.length) * 100
  const valuation = 100 - percentile

  // Trend: MA20 vs MA60; neutral (0) when history too short for MA60
  const trendRatio = seq.length >= 60 ? ma(seq, 20) / ma(seq, 60) - 1 : 0
  const trend = Math.max(0, Math.min(50 + trendRatio * TREND_K, 100))

  return { quality, valuation, trend, trendRatio, percentile, sharpe }
}

export type Signals = NonNullable<ReturnType<typeof computeSignals>>

/**
 * 门控结论：质量 → 趋势 → 估值，三层决策，不等权平均。
 * composite 是指针位置分（0–100），label/level 决定颜色和文字。
 */
export function signalVerdict(s: Signals): {
  label: string; level: number; composite: number; reason: string
} {
  const { quality, valuation, trendRatio } = s

  if (quality === null || quality < QUALITY_FLOOR)
    return { label: '观望', level: 2, composite: 50, reason: '质量不达标' }

  if (trendRatio < -TREND_EPS)
    return { label: '卖出', level: 1, composite: 25, reason: '质量达标·趋势向下' }

  if (trendRatio > TREND_EPS) {
    if (valuation >= CHEAP)
      return { label: '强烈买入', level: 4, composite: 90, reason: '质量达标·趋势向上·估值便宜' }
    if (valuation <= EXPENSIVE)
      return { label: '持有', level: 2, composite: 58, reason: '质量达标·趋势向上·估值偏贵' }
    return { label: '买入', level: 3, composite: 72, reason: '质量达标·趋势向上' }
  }

  // neutral trend
  if (valuation >= CHEAP)
    return { label: '买入(左侧)', level: 3, composite: 65, reason: '质量达标·趋势中性·估值便宜' }
  return { label: '持有', level: 2, composite: 52, reason: '质量达标·趋势中性' }
}
