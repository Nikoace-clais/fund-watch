import type { FC } from 'react'
import { CheckCircle2, Loader2 } from 'lucide-react'
import type { OcrStep } from '@/services/import'

const STEPS: { key: OcrStep['step']; label: string }[] = [
  { key: 'ocr', label: '识别图片文字' },
  { key: 'ai_extract', label: 'AI 提取基金名称' },
  { key: 'search', label: '搜索基金数据库' },
  { key: 'pro_identify', label: 'Pro 识别未命中基金' },
  { key: 'pro_review', label: 'Pro 核查匹配结果' },
]

export const OcrProgress: FC<{
  currentStep: OcrStep | null
  onCancel?: () => void
}> = ({ currentStep, onCancel }) => {
  const activeIdx = currentStep
    ? STEPS.findIndex((s) => s.key === currentStep.step)
    : 0

  return (
    <div className="flex flex-col items-center justify-center p-10 space-y-6">
      <Loader2 className="w-10 h-10 text-blue-500 animate-spin" />
      <p className="text-sm font-medium text-slate-700">
        {currentStep?.text ?? '准备中...'}
      </p>
      <ol className="w-full max-w-xs space-y-2">
        {STEPS.map((s, i) => {
          const done = i < activeIdx
          const active = i === activeIdx && !!currentStep
          return (
            <li key={s.key} className="flex items-center gap-2 text-sm">
              {done ? (
                <CheckCircle2 className="w-4 h-4 text-green-500 shrink-0" />
              ) : active ? (
                <Loader2 className="w-4 h-4 text-blue-500 animate-spin shrink-0" />
              ) : (
                <span className="w-4 h-4 rounded-full border border-slate-300 shrink-0" />
              )}
              <span
                className={
                  done
                    ? 'text-slate-400 line-through'
                    : active
                      ? 'text-slate-900 font-medium'
                      : 'text-slate-400'
                }
              >
                {s.label}
              </span>
            </li>
          )
        })}
      </ol>
      {onCancel && (
        <button
          onClick={onCancel}
          className="text-sm text-slate-400 hover:text-slate-700 transition-colors"
        >
          取消
        </button>
      )}
    </div>
  )
}
