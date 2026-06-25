import { Outlet, Link, useLocation } from 'react-router'
import { LineChart, PieChart, TrendingUp, Home, Menu, X, Settings, Sparkles, Camera } from 'lucide-react'
import { useState, useRef, useEffect } from 'react'
import { cn } from '@/lib/utils'
import { useColor, type ColorScheme } from '@/lib/color-context'
import { useCronStatus } from '@/lib/queries'

const navigation = [
  { name: '概览', href: '/', icon: Home },
  { name: '自选基金', href: '/portfolio', icon: PieChart },
  { name: '行情数据', href: '/market', icon: TrendingUp },
  { name: 'AI 选基', href: '/ai-select', icon: Sparkles },
  { name: '截图导入', href: '/import', icon: Camera },
]

function ColorSchemeSetting() {
  const { scheme, setScheme } = useColor()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const options: { value: ColorScheme; label: string; desc: string }[] = [
    { value: 'red-up', label: '红涨绿跌', desc: 'A股习惯' },
    { value: 'green-up', label: '绿涨红跌', desc: '国际惯例' },
  ]

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className={cn(
          'flex items-center w-full px-3 py-2.5 rounded-md text-sm font-medium transition-colors',
          'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
        )}
      >
        <Settings className="mr-3 h-5 w-5 text-slate-400" />
        设置
      </button>

      {open && (
        <div className="absolute bottom-full left-0 mb-2 w-56 bg-white rounded-xl border border-slate-200 shadow-lg p-3 z-50">
          <p className="text-xs font-medium text-slate-400 uppercase mb-2">涨跌配色</p>
          <div className="space-y-1">
            {options.map((opt) => (
              <button
                key={opt.value}
                onClick={() => {
                  setScheme(opt.value)
                  setOpen(false)
                }}
                className={cn(
                  'w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors',
                  scheme === opt.value
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-slate-600 hover:bg-slate-50',
                )}
              >
                <div className="flex items-center gap-2">
                  <span className="flex gap-0.5">
                    <span className={cn(
                      'inline-block w-3 h-3 rounded-full',
                      opt.value === 'red-up' ? 'bg-red-500' : 'bg-green-500',
                    )} />
                    <span className={cn(
                      'inline-block w-3 h-3 rounded-full',
                      opt.value === 'red-up' ? 'bg-green-500' : 'bg-red-500',
                    )} />
                  </span>
                  <span>{opt.label}</span>
                </div>
                <span className="text-xs text-slate-400">{opt.desc}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function CronStatusBadge() {
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

export function Layout() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)
  const location = useLocation()
  // 侧边栏在移动端隐藏,cron 失败时在 header 菜单按钮上加红点提示
  const { data: cronStatus } = useCronStatus()
  const cronFailed = !!cronStatus?.last_error

  return (
    <div className="flex h-screen bg-slate-50 text-slate-900 overflow-hidden">
      {/* Sidebar */}
      <aside className="hidden w-64 border-r border-slate-200 bg-white md:flex md:flex-col">
        <div className="flex h-16 items-center px-6 border-b border-slate-200">
          <LineChart className="h-6 w-6 text-blue-600 mr-2" />
          <span className="text-xl font-bold text-slate-800 tracking-tight">智投基金</span>
        </div>
        <nav className="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
          {navigation.map((item) => {
            const isActive = location.pathname === item.href
            return (
              <Link
                key={item.name}
                to={item.href}
                className={cn(
                  'flex items-center px-3 py-2.5 rounded-md text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
                )}
              >
                <item.icon
                  className={cn('mr-3 h-5 w-5 flex-shrink-0', isActive ? 'text-blue-600' : 'text-slate-400')}
                />
                {item.name}
              </Link>
            )
          })}
        </nav>
        {/* Cron + Settings at bottom */}
        <div className="px-4 pb-4 border-t border-slate-100 pt-3 space-y-1">
          <CronStatusBadge />
          <ColorSchemeSetting />
        </div>
      </aside>

      {/* Mobile */}
      <div className="flex flex-col flex-1 overflow-hidden w-full">
        <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-4 md:hidden shrink-0">
          <div className="flex items-center">
            <LineChart className="h-6 w-6 text-blue-600 mr-2" />
            <span className="text-xl font-bold text-slate-800">智投基金</span>
          </div>
          <button
            type="button"
            className="relative text-slate-500 hover:text-slate-600"
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
          >
            {isMobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
            {cronFailed && !isMobileMenuOpen && (
              <span
                className="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full bg-red-500"
                title="快照拉取失败"
              />
            )}
          </button>
        </header>

        {isMobileMenuOpen && (
          <div className="absolute top-16 left-0 right-0 z-50 bg-white border-b border-slate-200 shadow-lg md:hidden">
            <nav className="px-4 py-2 space-y-1">
              {navigation.map((item) => {
                const isActive = location.pathname === item.href
                return (
                  <Link
                    key={item.name}
                    to={item.href}
                    onClick={() => setIsMobileMenuOpen(false)}
                    className={cn(
                      'flex items-center px-3 py-3 rounded-md text-base font-medium',
                      isActive
                        ? 'bg-blue-50 text-blue-700'
                        : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900',
                    )}
                  >
                    <item.icon
                      className={cn('mr-4 h-5 w-5 flex-shrink-0', isActive ? 'text-blue-600' : 'text-slate-400')}
                    />
                    {item.name}
                  </Link>
                )
              })}
            </nav>
            {/* Mobile settings */}
            <div className="px-4 pb-3 border-t border-slate-100 pt-2">
              {cronFailed && (
                <p className="px-3 py-1.5 text-xs text-red-500 truncate" title={cronStatus?.last_error ?? undefined}>
                  ⚠ 快照拉取失败
                </p>
              )}
              <ColorSchemeSetting />
            </div>
          </div>
        )}

        <main className="flex-1 overflow-y-auto bg-slate-50/50 p-4 md:p-8 w-full relative">
          <div className="max-w-7xl mx-auto w-full">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
