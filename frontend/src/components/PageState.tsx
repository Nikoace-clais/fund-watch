import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

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
