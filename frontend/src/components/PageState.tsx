import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

/**
 * 统一的页面加载/空态占位。
 * loading 优先于 empty;两者都为假时渲染 null(调用方负责渲染正文)。
 */
export function PageState({
  loading,
  empty,
  emptyContent = '暂无数据',
  className,
}: {
  loading?: boolean
  empty?: boolean
  emptyContent?: ReactNode
  className?: string
}) {
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
