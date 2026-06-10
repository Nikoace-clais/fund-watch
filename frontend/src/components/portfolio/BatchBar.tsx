import { Trash2 } from 'lucide-react'

export function BatchBar({
  count,
  onDelete,
  onClear,
  deleting,
}: {
  count: number
  onDelete: () => void
  onClear: () => void
  deleting: boolean
}) {
  if (count === 0) return null
  return (
    <div className="flex items-center gap-4 px-6 py-2.5 bg-blue-50 border-b border-blue-100">
      <span className="text-sm font-medium text-blue-700">已选 {count} 只基金</span>
      <div className="flex-1" />
      <button
        onClick={onDelete}
        disabled={deleting}
        className="inline-flex items-center gap-1.5 text-sm font-medium text-red-600 hover:text-red-700 disabled:opacity-50 transition-colors"
      >
        <Trash2 className="h-3.5 w-3.5" />
        删除选中
      </button>
      <button
        onClick={onClear}
        className="text-sm text-slate-500 hover:text-slate-700 transition-colors"
      >
        取消
      </button>
    </div>
  )
}
