import { Link } from 'react-router'
import { useState } from 'react'
import { TrendingUp, ArrowRight, BarChart3, Briefcase, Camera, Activity, Plus } from 'lucide-react'
import { useFundsOverview, useMarketIndices, usePortfolioSummary } from '@/lib/queries'
import { useSelectedPortfolio } from '@/lib/portfolio-context'
import { cn, formatCNY, formatNum2, formatPercent } from '@/lib/utils'
import { useColor } from '@/lib/color-context'
import { PageState } from '@/components/PageState'
import { AddFundModal } from '@/components/AddFundModal'

/* ---------- A-share display codes for header badges ---------- */
const BADGE_CODES = ['000001', '399001', '399006']

/* ---------- component ---------- */
export function Dashboard() {
  const { colorFor, badgeClassFor } = useColor()
  const { selectedId } = useSelectedPortfolio()
  const { data: overview = [], isLoading: loading } = useFundsOverview()
  const { data: portfolio } = usePortfolioSummary(selectedId)
  const { data: allIndices = [], isLoading: indicesLoading } = useMarketIndices()
  const [showAddModal, setShowAddModal] = useState(false)

  const indices = allIndices
    .filter((i) => BADGE_CODES.includes(i.code))
    .sort((a, b) => BADGE_CODES.indexOf(a.code) - BADGE_CODES.indexOf(b.code))

  const topFunds = overview.slice(0, 4)

  /* 自选涨跌分布(基于盘中估算涨跌幅) */
  const changes = overview
    .map((it) => it.latest?.gszzl)
    .filter((v): v is number => v != null)
  const upCount = changes.filter((v) => v > 0).length
  const downCount = changes.filter((v) => v < 0).length

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
            return (
              <span
                key={idx.code}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium border',
                  badgeClassFor(idx.change_percent),
                )}
              >
                {idx.name}
                <span className="font-semibold">{formatNum2(idx.value)}</span>
                <span>{up ? '+' : ''}{idx.change_percent.toFixed(2)}%</span>
              </span>
            )
          })}
          {indices.length === 0 && !indicesLoading && (
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

        {/* watchlist up/down distribution */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
          <div className="flex items-center gap-2 text-slate-500 text-sm mb-2">
            <Activity className="h-4 w-4" />
            自选涨跌分布(估算)
          </div>
          {changes.length > 0 ? (
            <div className="flex items-baseline gap-4">
              <p className="text-2xl font-bold">
                <span className={colorFor(1)}>{upCount}</span>
                <span className="text-sm font-medium text-slate-400 ml-1">涨</span>
              </p>
              <p className="text-2xl font-bold">
                <span className={colorFor(-1)}>{downCount}</span>
                <span className="text-sm font-medium text-slate-400 ml-1">跌</span>
              </p>
              {changes.length - upCount - downCount > 0 && (
                <p className="text-2xl font-bold">
                  <span className="text-gray-500">{changes.length - upCount - downCount}</span>
                  <span className="text-sm font-medium text-slate-400 ml-1">平</span>
                </p>
              )}
            </div>
          ) : (
            <p className="text-2xl font-bold text-slate-900">—</p>
          )}
        </div>
      </div>

      {/* ---- Quick actions ---- */}
      <div className="flex gap-3">
        <button
          onClick={() => setShowAddModal(true)}
          className="inline-flex items-center gap-2 px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
        >
          <Plus className="h-4 w-4" />
          添加基金
        </button>
        <Link
          to="/import"
          className="inline-flex items-center gap-2 px-4 py-2.5 bg-white border border-slate-200 text-slate-700 rounded-lg hover:bg-slate-50 transition-colors font-medium"
        >
          <Camera className="h-4 w-4" />
          截图导入
        </Link>
      </div>

      <AddFundModal
        open={showAddModal}
        onClose={() => setShowAddModal(false)}
        portfolioId={selectedId}
        existingCodes={overview.map((i) => i.fund.code)}
      />

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

        <PageState
          loading={loading}
          empty={topFunds.length === 0}
          className="py-16"
          emptyContent={
            <span>
              暂无自选基金，
              <Link to="/portfolio" className="text-blue-600 hover:underline">
                去添加
              </Link>
            </span>
          }
        />
        {!loading && topFunds.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {topFunds.map(({ fund, latest }) => {
              const name = latest?.name || fund.name || fund.code
              const gsz = latest?.gsz
              const gszzl = latest?.gszzl
              const dwjz = latest?.dwjz
              // dwjz 缺失时回退到盘中估算值,必须明确标注为估算
              const isEstimate = dwjz == null && gsz != null

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
                      <p className="text-xs text-slate-400 flex items-center gap-1">
                        单位净值
                        {isEstimate && (
                          <span
                            className="inline-flex items-center px-1 rounded bg-blue-50 text-blue-600 border border-blue-200 text-[10px] leading-4 cursor-help"
                            title={latest?.gztime ? `盘中估算值 · ${latest.gztime}` : '盘中估算值'}
                          >
                            估
                          </span>
                        )}
                      </p>
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
