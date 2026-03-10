import { useState, useEffect } from 'react'
import { X } from 'lucide-react'
import { addTransaction, fetchFundDetail, fetchNavOnDate } from '@/lib/api'
import { cn } from '@/lib/utils'

type Props = {
  open: boolean
  onClose: () => void
  onSaved: () => void
  code: string
  name?: string
  defaultNav?: number
}

export function HoldingEditModal({ open, onClose, onSaved, code, name, defaultNav }: Props) {
  const today = new Date().toISOString().slice(0, 10)

  const [direction, setDirection] = useState<'buy' | 'sell'>('buy')
  const [tradeDate, setTradeDate] = useState(today)
  const [nav, setNav] = useState(defaultNav ? defaultNav.toFixed(4) : '')
  const [shares, setShares] = useState('')
  const [fee, setFee] = useState('0')
  const [feeRate, setFeeRate] = useState<number | null>(null)
  const [feeManual, setFeeManual] = useState(false)
  const [navLoading, setNavLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // reset + fetch fee rate when opened
  useEffect(() => {
    if (!open) return
    setDirection('buy')
    setTradeDate(today)
    setNav(defaultNav ? defaultNav.toFixed(4) : '')
    setShares('')
    setFee('0')
    setFeeManual(false)
    setFeeRate(null)
    setError(null)

    fetchFundDetail(code).then((d) => {
      // prefer discounted rate (天天基金优惠), fall back to original
      const rate = d.subscription_rate ?? null
      setFeeRate(rate)
    }).catch(() => {/* silently ignore */})
  }, [open, code]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onClose])

  // fetch NAV when date changes
  useEffect(() => {
    if (!open || !tradeDate || !code) return
    setNavLoading(true)
    fetchNavOnDate(code, tradeDate)
      .then((d) => { if (d.nav != null) setNav(d.nav.toFixed(4)) })
      .catch(() => {/* keep current value */})
      .finally(() => setNavLoading(false))
  }, [tradeDate, code, open])

  const navNum = parseFloat(nav)
  const sharesNum = parseFloat(shares)
  const amount = nav && shares && !isNaN(navNum) && !isNaN(sharesNum)
    ? navNum * sharesNum
    : null

  // auto-compute fee when amount or rate changes (buy only), unless user edited manually
  useEffect(() => {
    if (feeManual || direction !== 'buy' || amount === null || feeRate === null) return
    setFee((amount * feeRate / 100).toFixed(2))
  }, [amount, feeRate, direction, feeManual])

  // when switching to sell, reset fee to 0 (user fills manually)
  useEffect(() => {
    if (direction === 'sell') { setFee('0'); setFeeManual(false) }
  }, [direction])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    if (!nav || !shares) { setError('请填写净值和份额'); return }
    setSubmitting(true)
    try {
      await addTransaction(code, { direction, trade_date: tradeDate, nav, shares, fee })
      onSaved()
      onClose()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '提交失败')
    } finally {
      setSubmitting(false)
    }
  }

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4">
        {/* header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <div>
            <h2 className="text-base font-semibold text-slate-900">记录持仓</h2>
            <p className="text-xs text-slate-400 mt-0.5">{name || code} · {code}</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 transition-colors">
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          {/* direction */}
          <div className="flex rounded-lg overflow-hidden border border-slate-200">
            {(['buy', 'sell'] as const).map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => setDirection(d)}
                className={cn(
                  'flex-1 py-2 text-sm font-medium transition-colors',
                  direction === d
                    ? d === 'buy'
                      ? 'bg-red-500 text-white'
                      : 'bg-green-500 text-white'
                    : 'text-slate-500 hover:bg-slate-50',
                )}
              >
                {d === 'buy' ? '买入' : '卖出'}
              </button>
            ))}
          </div>

          {/* date + nav */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-500 mb-1">交易日期</label>
              <input
                type="date"
                value={tradeDate}
                onChange={(e) => setTradeDate(e.target.value)}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">
                成交净值{navLoading && <span className="ml-1 text-blue-400">获取中…</span>}
              </label>
              <input
                type="number"
                step="0.0001"
                min="0"
                value={nav}
                onChange={(e) => setNav(e.target.value)}
                placeholder="例：1.2345"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* shares + fee */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-500 mb-1">份额</label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={shares}
                onChange={(e) => setShares(e.target.value)}
                placeholder="例：1000.00"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">
                手续费（元）
                {feeRate !== null && direction === 'buy' && (
                  <span className="ml-1 text-blue-400">· 已按 {feeRate}% 自动计算</span>
                )}
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={fee}
                onChange={(e) => { setFee(e.target.value); setFeeManual(true) }}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* amount preview */}
          <div className="rounded-lg bg-slate-50 px-4 py-3 flex items-center justify-between text-sm">
            <span className="text-slate-500">交易金额（预估）</span>
            <span className="font-semibold text-slate-800">
              {amount !== null ? `¥${amount.toFixed(2)}` : '—'}
            </span>
          </div>

          {error && (
            <p className="text-sm text-red-500 text-center">{error}</p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className={cn(
              'w-full py-2.5 rounded-xl text-sm font-medium transition-colors',
              direction === 'buy'
                ? 'bg-red-500 hover:bg-red-600 text-white'
                : 'bg-green-500 hover:bg-green-600 text-white',
              submitting && 'opacity-50 cursor-not-allowed',
            )}
          >
            {submitting ? '提交中...' : direction === 'buy' ? '确认买入' : '确认卖出'}
          </button>
        </form>
      </div>
    </div>
  )
}
