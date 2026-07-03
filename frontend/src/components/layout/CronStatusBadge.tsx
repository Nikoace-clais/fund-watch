import { cn } from '@/lib/utils'
import { useCronStatus } from '@/lib/queries'

export function CronStatusBadge() {
  const { data: status } = useCronStatus()

  if (!status) return null

  const lastTime = status.last_pull_at
    ? new Date(status.last_pull_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    : null

  return (
    <div className="px-3 pt-2 pb-1 text-xs text-slate-400 space-y-0.5">
      <div className="flex items-center gap-1.5">
        <span className={cn('h-1.5 w-1.5 rounded-full shrink-0', status.is_active ? 'bg-green-400 animate-pulse' : 'bg-slate-300')} />
        <span className="truncate">{status.is_active ? '拉取中' : '开市自动拉取'}</span>
        {status.pull_count > 0 && (
          <span className="ml-auto shrink-0 tabular-nums">{status.pull_count}次</span>
        )}
      </div>
      {lastTime && (
        <p className="pl-3 text-slate-300">最近 {lastTime}</p>
      )}
      {status.last_error && (
        <p className="pl-3 text-red-300 truncate" title={status.last_error}>⚠ 上次失败</p>
      )}
    </div>
  )
}
