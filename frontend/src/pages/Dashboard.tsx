import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { TrendingUp, ArrowRight, BarChart3, Briefcase } from 'lucide-react'
import { fetchFundsOverview, fetchPortfolioSummary, fetchMarketIndices } from '@/lib/api'
import { cn, formatCNY, formatPercent } from '@/lib/utils'
import { useColor } from '@/lib/color-context'

/* ---------- types ---------- */
type OverviewItem = {
  fund: { code: string; name?: string; sector?: string }
  latest?: { gsz?: number; gszzl?: number; name?: string; dwjz?: number; gztime?: string } | null
}

type PortfolioSummary = {
  total_current: string
  total_daily_return: string
  fund_count: number
}

/* ---------- A-share display codes for header badges ---------- */
const BADGE_CODES = ['000001', '399001', '399006']

type IndexBadge = { code: string; name: string; value: number; change_percent: number }

/* ---------- component ---------- */
export function Dashboard() {
  const { colorFor } = useColor()
  const [overview, setOverview] = useState<OverviewItem[]>([])
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null)
  const [indices, setIndices] = useState<IndexBadge[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      try {
        const [ov, ps, idx] = await Promise.allSettled([
          fetchFundsOverview(),
          fetchPortfolioSummary(),
          fetchMarketIndices(),
        ])
        if (ov.status === 'fulfilled') setOverview(ov.value.items)
        if (ps.status === 'fulfilled') setPortfolio(ps.value)
        if (idx.status === 'fulfilled') {
          setIndices(
            idx.value.items
              .filter((i) => BADGE_CODES.includes(i.code))
              .sort((a, b) => BADGE_CODES.indexOf(a.code) - BADGE_CODES.indexOf(b.code))
          )
        }
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const topFunds = overview.slice(0, 4)

  /* helpers */
  const hasCurrency = (v: string | undefined) => v && parseFloat(v) !== 0

  return (
    <div className="space-y-8">
      {/* ---- Header row ---- */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">市场概览</h1>
          <p className="text-sm text-slate-500 mt-1">实时估值与自选基金快报</p>
        </div>

        {/* market indices */}
        <div className="flex gap-3 flex-wrap">
          {indices.map((idx) => {
            const up = idx.change_percent > 0
            const zero = idx.change_percent === 0
            return (
              <span
                key={idx.code}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium border',
                  zero
                    ? 'bg-gray-50 text-gray-600 border-gray-200'
                    : colorFor(idx.change_percent).includes('red')
                      ? 'bg-red-50 text-red-600 border-red-200'
                      : 'bg-green-50 text-green-600 border-green-200',
                )}
              >
                {idx.name}
                <span className="font-semibold">{idx.value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                <span>{up ? '+' : ''}{idx.change_percent.toFixed(2)}%</span>
              </span>
            )
          })}
          {indices.length === 0 && !loading && (
            <span className="text-xs text-slate-400">指数数据暂不可用</span>
          )}
        </div>
      </div>

      {/* ---- Stat cards ---- */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
        {/* total assets */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
          <div className="flex items-center gap-2 text-slate-500 text-sm mb-2">
            <Briefcase className="h-4 w-4" />
            自选基金总资产(预估)
          </div>
          <p className="text-2xl font-bold text-slate-900">
            {portfolio && hasCurrency(portfolio.total_current)
              ? formatCNY(parseFloat(portfolio.total_current))
              : '—'}
          </p>
        </div>

        {/* daily return */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
          <div className="flex items-center gap-2 text-slate-500 text-sm mb-2">
            <TrendingUp className="h-4 w-4" />
            今日总收益(预估)
          </div>
          {portfolio && hasCurrency(portfolio.total_daily_return) ? (
            <p
              className={cn(
                'text-2xl font-bold',
                colorFor(parseFloat(portfolio.total_daily_return)),
              )}
            >
              {formatCNY(parseFloat(portfolio.total_daily_return))}
            </p>
          ) : (
            <p className="text-2xl font-bold text-slate-900">—</p>
          )}
        </div>

        {/* market heat — placeholder, hidden until real signal is implemented */}
      </div>

      {/* ---- Hot funds section ---- */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-slate-700" />
            <h2 className="text-lg font-semibold text-slate-800">自选基金概览</h2>
          </div>
          <Link
            to="/portfolio"
            className="inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700 font-medium"
          >
            查看全部 <ArrowRight className="h-4 w-4" />
          </Link>
        </div>

        {loading ? (
          <div className="text-center py-16 text-slate-400">加载中...</div>
        ) : topFunds.length === 0 ? (
          <div className="text-center py-16 text-slate-400">
            暂无自选基金，
            <Link to="/portfolio" className="text-blue-600 hover:underline">
              去添加
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {topFunds.map(({ fund, latest }) => {
              const name = latest?.name || fund.name || fund.code
              const gsz = latest?.gsz
              const gszzl = latest?.gszzl
              const dwjz = latest?.dwjz

              return (
                <Link
                  key={fund.code}
                  to={`/funds/${fund.code}`}
                  className={cn(
                    'bg-white rounded-xl border border-slate-200 p-6 shadow-sm',
                    'transition-all hover:shadow-lg hover:border-blue-300',
                  )}
                >
                  {/* fund name */}
                  <h3 className="text-base font-semibold text-slate-900 truncate">{name}</h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {fund.code}
                    {fund.sector ? ` | ${fund.sector}` : ''}
                  </p>

                  {/* nav */}
                  <div className="mt-4 flex items-baseline justify-between">
                    <div>
                      <p className="text-xs text-slate-400">单位净值</p>
                      <p className="text-lg font-bold text-slate-800">
                        {dwjz != null ? dwjz.toFixed(4) : gsz != null ? gsz.toFixed(4) : '—'}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-slate-400">日涨跌幅</p>
                      {gszzl != null ? (
                        <p className={cn('text-lg font-bold', colorFor(gszzl))}>
                          {formatPercent(gszzl)}
                        </p>
                      ) : (
                        <p className="text-lg font-bold text-slate-300">—</p>
                      )}
                    </div>
                  </div>
                </Link>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
