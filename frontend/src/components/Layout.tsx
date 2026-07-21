import { Outlet, Link, useLocation } from 'react-router'
import {
  LineChart,
  PieChart,
  TrendingUp,
  Home,
  Menu,
  X,
  Sparkles,
  Camera,
  Search,
} from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/lib/utils'
import { useCronStatus } from '@/lib/queries'
import { AiConfigSetting } from './layout/AiConfigSetting'
import { ColorSchemeSetting } from './layout/ColorSchemeSetting'
import { CronStatusBadge } from './layout/CronStatusBadge'
import { TokenSetting } from './layout/TokenSetting'

const navigation = [
  { name: '概览', href: '/', icon: Home, testid: 'nav-overview' },
  {
    name: '自选基金',
    href: '/portfolio',
    icon: PieChart,
    testid: 'nav-portfolio',
  },
  { name: '行情数据', href: '/market', icon: TrendingUp, testid: 'nav-market' },
  {
    name: 'AI 选基',
    href: '/ai-select',
    icon: Sparkles,
    testid: 'nav-ai-select',
  },
  { name: '截图导入', href: '/import', icon: Camera, testid: 'nav-import' },
  {
    name: '持仓反查',
    href: '/stock-funds',
    icon: Search,
    testid: 'nav-stock-funds',
  },
]

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
          <span className="text-xl font-bold text-slate-800 tracking-tight">
            智投基金
          </span>
        </div>
        <nav className="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
          {navigation.map((item) => {
            const isActive = location.pathname === item.href
            return (
              <Link
                key={item.name}
                to={item.href}
                data-testid={item.testid}
                className={cn(
                  'flex items-center px-3 py-2.5 rounded-md text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
                )}
              >
                <item.icon
                  className={cn(
                    'mr-3 h-5 w-5 flex-shrink-0',
                    isActive ? 'text-blue-600' : 'text-slate-400',
                  )}
                />
                {item.name}
              </Link>
            )
          })}
        </nav>
        {/* Cron + Settings at bottom */}
        <div className="px-4 pb-4 border-t border-slate-100 pt-3 space-y-1">
          <CronStatusBadge />
          <AiConfigSetting />
          <TokenSetting />
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
            {isMobileMenuOpen ? (
              <X className="h-6 w-6" />
            ) : (
              <Menu className="h-6 w-6" />
            )}
            {cronFailed && !isMobileMenuOpen && (
              <span
                className="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full bg-red-500"
                title="快照拉取失败"
              />
            )}
          </button>
        </header>

        {isMobileMenuOpen && (
          <>
            {/* 透明遮罩：点击菜单外区域关闭菜单 */}
            <div
              className="fixed inset-0 z-40 md:hidden"
              onClick={() => setIsMobileMenuOpen(false)}
            />
            <div className="absolute top-16 left-0 right-0 z-50 bg-white border-b border-slate-200 shadow-lg md:hidden">
              <nav className="px-4 py-2 space-y-1">
                {navigation.map((item) => {
                  const isActive = location.pathname === item.href
                  return (
                    <Link
                      key={item.name}
                      to={item.href}
                      data-testid={item.testid}
                      onClick={() => setIsMobileMenuOpen(false)}
                      className={cn(
                        'flex items-center px-3 py-3 rounded-md text-base font-medium',
                        isActive
                          ? 'bg-blue-50 text-blue-700'
                          : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900',
                      )}
                    >
                      <item.icon
                        className={cn(
                          'mr-4 h-5 w-5 flex-shrink-0',
                          isActive ? 'text-blue-600' : 'text-slate-400',
                        )}
                      />
                      {item.name}
                    </Link>
                  )
                })}
              </nav>
              {/* Mobile settings */}
              <div className="px-4 pb-3 border-t border-slate-100 pt-2">
                {cronFailed && (
                  <p
                    className="px-3 py-1.5 text-xs text-red-500 truncate"
                    title={cronStatus?.last_error ?? undefined}
                  >
                    ⚠ 快照拉取失败
                  </p>
                )}
                <AiConfigSetting />
                <TokenSetting />
                <ColorSchemeSetting />
              </div>
            </div>
          </>
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
