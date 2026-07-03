import type { ReactNode } from 'react'
import { AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

/** 统一的行内错误/警告横幅（图标 + 浅色底 + 圆角边框）。 */
export function ErrorBanner({
  variant = 'error',
  className,
  children,
}: {
  variant?: 'error' | 'warning'
  className?: string
  children: ReactNode
}) {
  return (
    <div
      className={cn(
        'flex items-center gap-2 px-4 py-3 border rounded-xl text-sm',
        variant === 'error'
          ? 'bg-red-50 border-red-200 text-red-600'
          : 'bg-amber-50 border-amber-200 text-amber-700',
        className,
      )}
    >
      <AlertCircle className="h-4 w-4 shrink-0" />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  )
}

/** 「估」徽标：明确标注数值为盘中估算而非最终净值。 */
export function EstimateBadge({ time }: { time?: string | null }) {
  return (
    <span
      className="inline-flex items-center px-1 rounded bg-blue-50 text-blue-600 border border-blue-200 text-[10px] leading-4 cursor-help"
      title={time ? `盘中估算值 · ${time}` : '盘中估算值'}
    >
      估
    </span>
  )
}

/**
 * 统一的页面加载/空态/错误占位。
 * 优先级 error > loading > empty;三者都为假时渲染 null(调用方负责渲染正文)。
 */
export function PageState({
  loading,
  empty,
  error,
  emptyContent = '暂无数据',
  errorContent = '加载失败，请稍后重试',
  className,
}: {
  loading?: boolean
  empty?: boolean
  error?: boolean
  emptyContent?: ReactNode
  errorContent?: ReactNode
  className?: string
}) {
  if (error) {
    return (
      <div className={cn('flex items-center justify-center py-32 text-red-400', className)}>
        {errorContent}
      </div>
    )
  }
  if (loading) {
    return (
      <div className={cn('flex items-center justify-center py-32 text-slate-400', className)}>
        加载中...
      </div>
    )
  }
  if (empty) {
    return (
      <div className={cn('flex items-center justify-center py-32 text-slate-400', className)}>
        {emptyContent}
      </div>
    )
  }
  return null
}
