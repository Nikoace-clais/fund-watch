import { Outlet, Link, useLocation } from 'react-router'
import { LineChart, PieChart, TrendingUp, Home, Menu, X, Settings } from 'lucide-react'
import { useState, useRef, useEffect } from 'react'
import { cn } from '@/lib/utils'
import { useColor, type ColorScheme } from '@/lib/color-context'

const navigation = [
  { name: '概览', href: '/', icon: Home },
  { name: '自选基金', href: '/portfolio', icon: PieChart },
  { name: '行情数据', href: '/market', icon: TrendingUp },
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

export function Layout() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)
  const location = useLocation()

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
        {/* Settings at bottom */}
        <div className="px-4 pb-4 border-t border-slate-100 pt-3">
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
            className="text-slate-500 hover:text-slate-600"
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
          >
            {isMobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
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
