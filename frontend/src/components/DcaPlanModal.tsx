import { useState, useEffect } from 'react'
import { X } from 'lucide-react'
import { createDcaPlan } from '@/lib/api'
import { cn } from '@/lib/utils'

type Props = {
  open: boolean
  code: string
  name?: string
  onClose: () => void
  onSaved: () => void
}

const FREQ_OPTIONS = [
  { value: 'daily',    label: '每日' },
  { value: 'weekly',   label: '每周' },
  { value: 'biweekly', label: '每两周' },
  { value: 'monthly',  label: '每月' },
] as const

const WEEKDAYS = ['周一','周二','周三','周四','周五','周六','周日']

export function DcaPlanModal({ open, code, name, onClose, onSaved }: Props) {
  const today = new Date().toISOString().slice(0, 10)
  const [planName, setPlanName] = useState('')
  const [amount, setAmount] = useState('')
  const [frequency, setFrequency] = useState<'daily'|'weekly'|'biweekly'|'monthly'>('monthly')
  const [dayOfWeek, setDayOfWeek] = useState(0)
  const [dayOfMonth, setDayOfMonth] = useState(1)
  const [startDate, setStartDate] = useState(today)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setPlanName('')
    setAmount('')
    setFrequency('monthly')
    setDayOfWeek(0)
    setDayOfMonth(1)
    setStartDate(today)
    setError(null)
  }, [open])

  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onClose])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!amount || isNaN(parseFloat(amount))) { setError('请填写每期金额'); return }
    setSubmitting(true)
    try {
      await createDcaPlan({
        code,
        name: planName || undefined,
        amount,
        frequency,
        day_of_week: (frequency === 'weekly' || frequency === 'biweekly') ? dayOfWeek : undefined,
        day_of_month: frequency === 'monthly' ? dayOfMonth : undefined,
        start_date: startDate,
      })
      onSaved()
      onClose()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '创建失败')
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
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <div>
            <h2 className="text-base font-semibold text-slate-900">新建定投计划</h2>
            <p className="text-xs text-slate-400 mt-0.5">{name || code} · {code}</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 transition-colors">
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          {/* 备注名 */}
          <div>
            <label className="block text-xs text-slate-500 mb-1">备注名（可选）</label>
            <input
              type="text"
              value={planName}
              onChange={(e) => setPlanName(e.target.value)}
              placeholder="例：每月3号定投"
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* 每期金额 + 起始日期 */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-500 mb-1">每期金额（元）</label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="例：500"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">起始日期</label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* 频率 */}
          <div>
            <label className="block text-xs text-slate-500 mb-1">定投频率</label>
            <div className="flex rounded-lg overflow-hidden border border-slate-200">
              {FREQ_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setFrequency(opt.value)}
                  className={cn(
                    'flex-1 py-2 text-sm font-medium transition-colors',
                    frequency === opt.value
                      ? 'bg-blue-500 text-white'
                      : 'text-slate-500 hover:bg-slate-50',
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* 条件字段 */}
          {(frequency === 'weekly' || frequency === 'biweekly') && (
            <div>
              <label className="block text-xs text-slate-500 mb-1">执行星期</label>
              <div className="flex gap-1">
                {WEEKDAYS.map((d, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => setDayOfWeek(i)}
                    className={cn(
                      'flex-1 py-1.5 rounded text-xs font-medium transition-colors',
                      dayOfWeek === i ? 'bg-blue-500 text-white' : 'bg-slate-100 text-slate-500 hover:bg-slate-200',
                    )}
                  >
                    {d}
                  </button>
                ))}
              </div>
            </div>
          )}

          {frequency === 'monthly' && (
            <div>
              <label className="block text-xs text-slate-500 mb-1">每月几号（1-28）</label>
              <input
                type="number"
                min={1}
                max={28}
                value={dayOfMonth}
                onChange={(e) => setDayOfMonth(parseInt(e.target.value))}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          )}

          {error && <p className="text-sm text-red-500 text-center">{error}</p>}

          <button
            type="submit"
            disabled={submitting}
            className={cn(
              'w-full py-2.5 rounded-xl text-sm font-medium transition-colors bg-blue-500 hover:bg-blue-600 text-white',
              submitting && 'opacity-50 cursor-not-allowed',
            )}
          >
            {submitting ? '创建中...' : '创建计划'}
          </button>
        </form>
      </div>
    </div>
  )
}
