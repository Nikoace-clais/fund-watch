import { useState } from 'react'
import { Check, AlertCircle } from 'lucide-react'
import { useAddFund } from '@/lib/queries'
import { cn, isFundCode } from '@/lib/utils'

export function CodeTab({ portfolioId }: { portfolioId?: number }) {
  const [code, setCode] = useState('')
  const [message, setMessage] = useState<{
    type: 'success' | 'error'
    text: string
  } | null>(null)
  const addFund = useAddFund(portfolioId)

  const isValid = isFundCode(code)
  const loading = addFund.isPending

  const handleSubmit = () => {
    if (!isValid) return
    setMessage(null)
    const submittedCode = code
    addFund.mutate(submittedCode, {
      onSuccess: () => {
        setMessage({ type: 'success', text: `基金 ${submittedCode} 添加成功` })
        setCode('')
      },
      onError: (err: Error) =>
        setMessage({ type: 'error', text: err.message || '添加失败' }),
    })
  }

  return (
    <div className="space-y-4">
      <div>
        <label
          htmlFor="fund-code"
          className="block text-sm font-medium text-slate-600 mb-1.5"
        >
          基金代码
        </label>
        <div className="flex gap-2">
          <input
            id="fund-code"
            type="text"
            inputMode="numeric"
            value={code}
            onChange={(e) => {
              setCode(e.target.value.replace(/\D/g, '').slice(0, 6))
              setMessage(null)
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSubmit()
            }}
            placeholder="例如 110011"
            maxLength={6}
            className="flex-1 px-4 py-2.5 border border-slate-200 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <button
            onClick={handleSubmit}
            disabled={!isValid || loading}
            className={cn(
              'px-5 py-2.5 rounded-lg text-sm font-medium transition-colors',
              isValid && !loading
                ? 'bg-blue-600 text-white hover:bg-blue-700'
                : 'bg-slate-100 text-slate-400 cursor-not-allowed',
            )}
          >
            {loading ? '添加中...' : '添加'}
          </button>
        </div>
        {code.length > 0 && !isValid && (
          <p className="mt-1.5 text-xs text-slate-400">请输入6位数字基金代码</p>
        )}
      </div>

      {message && (
        <div
          className={cn(
            'flex items-center gap-2 text-sm px-3 py-2.5 rounded-lg',
            message.type === 'success'
              ? 'bg-green-50 text-green-700'
              : 'bg-red-50 text-red-600',
          )}
        >
          {message.type === 'success' ? (
            <Check className="w-4 h-4 shrink-0" />
          ) : (
            <AlertCircle className="w-4 h-4 shrink-0" />
          )}
          {message.text}
        </div>
      )}
    </div>
  )
}
