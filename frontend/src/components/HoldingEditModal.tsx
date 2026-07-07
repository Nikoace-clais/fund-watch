import { useState, useEffect } from 'react'
import { X } from 'lucide-react'
import { Modal } from './Modal'
import { fetchFundDetail, fetchFundPnl, fetchNavOnDate } from '@/lib/api'
import { useAddTransaction } from '@/lib/queries'
import { cn, todayLocal } from '@/lib/utils'

type Props = {
  open: boolean
  onClose: () => void
  code: string
  name?: string
  defaultNav?: number
  portfolioId?: number
}

export function HoldingEditModal({ open, onClose, code, name, defaultNav, portfolioId }: Props) {
  const today = todayLocal()
  const addTransaction = useAddTransaction(portfolioId)

  const [direction, setDirection] = useState<'buy' | 'sell'>('buy')
  const [tradeDate, setTradeDate] = useState(today)
  const [nav, setNav] = useState(defaultNav ? defaultNav.toFixed(4) : '')
  const [shares, setShares] = useState('')
  const [amount, setAmount] = useState('')
  const [holdingShares, setHoldingShares] = useState<string | null>(null)
  const [fee, setFee] = useState('0')
  const [feeRate, setFeeRate] = useState<number | null>(null)
  const [feeManual, setFeeManual] = useState(false)
  const [navLoading, setNavLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // reset + fetch fee rate when opened
  useEffect(() => {
    if (!open) return
    setDirection('buy')
    setTradeDate(today)
    setNav(defaultNav ? defaultNav.toFixed(4) : '')
    setShares('')
    setAmount('')
    setHoldingShares(null)
    setFee('0')
    setFeeManual(false)
    setFeeRate(null)
    setError(null)

    fetchFundDetail(code).then((d) => {
      // prefer discounted rate (天天基金优惠), fall back to original
      const rate = d.subscription_rate_discounted ?? d.subscription_rate ?? null
      setFeeRate(rate)
    }).catch(() => {/* silently ignore */})

    fetchFundPnl(code, portfolioId).then((d) => {
      setHoldingShares(d.holding_shares ?? null)
    }).catch(() => {/* silently ignore */})
  }, [open, code, defaultNav, portfolioId])

  // fetch NAV when date changes
  useEffect(() => {
    if (!open || !tradeDate || !code) return
    setNavLoading(true)
    fetchNavOnDate(code, tradeDate)
      .then((d) => {
        if (d.nav == null) return
        setNav(d.nav.toFixed(4))
        const s = parseFloat(shares)
        if (!isNaN(s)) setAmount((d.nav * s).toFixed(2))
      })
      .catch(() => {/* keep current value */})
      .finally(() => setNavLoading(false))
  }, [tradeDate, code, open])

  // amount <-> shares two-way sync
  const onNavChange = (v: string) => {
    setNav(v)
    const n = parseFloat(v)
    const s = parseFloat(shares)
    if (!isNaN(n) && !isNaN(s)) setAmount((n * s).toFixed(2))
  }
  const onSharesChange = (v: string) => {
    setShares(v)
    const n = parseFloat(nav)
    const s = parseFloat(v)
    if (!isNaN(n) && !isNaN(s)) setAmount((n * s).toFixed(2))
  }
  const onAmountChange = (v: string) => {
    setAmount(v)
    const n = parseFloat(nav)
    const a = parseFloat(v)
    if (!isNaN(n) && n > 0 && !isNaN(a)) setShares((a / n).toFixed(2))
  }

  const holdingSharesNum = holdingShares != null ? parseFloat(holdingShares) : NaN
  const applyPct = (pct: number | 'all') => {
    if (isNaN(holdingSharesNum) || holdingSharesNum <= 0 || holdingShares == null) return
    const newShares = pct === 'all' ? holdingShares : String(Math.floor(holdingSharesNum * pct * 100) / 100)
    setShares(newShares)
    const n = parseFloat(nav)
    const s = parseFloat(newShares)
    if (!isNaN(n) && !isNaN(s)) setAmount((n * s).toFixed(2))
  }

  // auto-compute fee when amount or rate changes (buy only), unless user edited manually
  useEffect(() => {
    if (feeManual || direction !== 'buy' || feeRate === null) return
    const amt = parseFloat(amount)
    if (isNaN(amt)) return
    setFee((amt * feeRate / 100).toFixed(2))
  }, [amount, feeRate, direction, feeManual])

  // when switching to sell, reset fee to 0 (user fills manually)
  useEffect(() => {
    if (direction === 'sell') { setFee('0'); setFeeManual(false) }
  }, [direction])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    if (!nav || !shares) { setError('请填写净值和份额'); return }
    addTransaction.mutate(
      { code, payload: { direction, trade_date: tradeDate, nav, shares, fee, portfolio_id: portfolioId } },
      {
        onSuccess: onClose,
        onError: (err: Error) => setError(err.message || '提交失败'),
      },
    )
  }
  const submitting = addTransaction.isPending

  return (
    <Modal open={open} onClose={onClose} className="rounded-2xl max-w-md">
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
                onChange={(e) => onNavChange(e.target.value)}
                placeholder="例：1.2345"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* shares + amount */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-500 mb-1">
                份额
                {direction === 'sell' && !isNaN(holdingSharesNum) && holdingSharesNum > 0 && (
                  <span className="ml-1 text-blue-400">可卖 {holdingShares}</span>
                )}
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={shares}
                onChange={(e) => onSharesChange(e.target.value)}
                placeholder="例：1000.00"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              {direction === 'sell' && !isNaN(holdingSharesNum) && holdingSharesNum > 0 && (
                <div className="flex gap-1.5 mt-1.5">
                  {([[0.25, '25%'], [0.5, '50%'], [0.75, '75%'], ['all', '全部']] as const).map(([pct, label]) => (
                    <button
                      key={label}
                      type="button"
                      onClick={() => applyPct(pct)}
                      className="flex-1 py-1 text-xs rounded border border-slate-200 text-slate-500 hover:bg-slate-50 transition-colors"
                    >
                      {label}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">交易金额（元）</label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={amount}
                onChange={(e) => onAmountChange(e.target.value)}
                placeholder="例：1234.56"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* fee */}
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
    </Modal>
  )
}
