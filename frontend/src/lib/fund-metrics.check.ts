/**
 * ponytail: one-shot self-check for signalVerdict gate logic.
 * run: bun frontend/src/lib/fund-metrics.check.ts
 * no frameworks, no fixtures — fails loud if the gate regresses.
 */
import assert from 'node:assert/strict'
import { signalVerdict } from './fund-metrics'

// (a) High quality + uptrend + expensive (near historical high) → 持有, NEVER 卖出
//     Regression guard: old model would score this as "卖出" due to high percentile
{
  const v = signalVerdict({ quality: 70, valuation: 20, trend: 65, trendRatio: 0.02, percentile: 80, sharpe: 1.4 })
  assert.notStrictEqual(v.label, '卖出',   'bull stock at new high must NOT be 卖出')
  assert.strictEqual(v.label,    '持有',   `expected 持有, got ${v.label}`)
}

// (b) Low quality + cheap → 观望, NEVER 买入
//     Regression guard: old model would score this as "买入" due to low percentile
{
  const v = signalVerdict({ quality: 10, valuation: 90, trend: 55, trendRatio: 0, percentile: 10, sharpe: 0.2 })
  assert.notStrictEqual(v.label, '买入',  'cheap but low-quality fund must NOT be 买入')
  assert.strictEqual(v.label,    '观望',  `expected 观望, got ${v.label}`)
}

// (c) High quality + uptrend + cheap (bounced off bottom) → 强烈买入
{
  const v = signalVerdict({ quality: 80, valuation: 80, trend: 75, trendRatio: 0.03, percentile: 20, sharpe: 1.6 })
  assert.strictEqual(v.label, '强烈买入', `expected 强烈买入, got ${v.label}`)
}

// (d) Downtrend regardless of valuation → 卖出
{
  const v = signalVerdict({ quality: 60, valuation: 85, trend: 35, trendRatio: -0.02, percentile: 15, sharpe: 1.2 })
  assert.strictEqual(v.label, '卖出', `expected 卖出 on downtrend, got ${v.label}`)
}

console.log('✓ fund-metrics signal verdict checks passed')
