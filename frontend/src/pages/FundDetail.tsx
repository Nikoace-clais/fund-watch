import { useState } from 'react'
import { useParams, useNavigate } from 'react-router'
import { ArrowLeft, Plus } from 'lucide-react'
import {
  useAddFund, useFundDetail, useFundHoldings, useNavHistory, useQuote, useTransactions,
} from '@/lib/queries'
import { useSelectedPortfolio } from '@/lib/portfolio-context'
import { HoldingEditModal } from '@/components/HoldingEditModal'
import { PageState } from '@/components/PageState'
import { NavChart } from '@/components/fund-detail/NavChart'
import { StageReturns } from '@/components/fund-detail/StageReturns'
import { AssetAllocationCard } from '@/components/fund-detail/AssetAllocationCard'
import { TopHoldings } from '@/components/fund-detail/TopHoldings'
import { TransactionsCard } from '@/components/fund-detail/TransactionsCard'
import { SignalGauge } from '@/components/fund-detail/SignalGauge'
import { RiskMetrics } from '@/components/fund-detail/RiskMetrics'
import { cn, formatPercent } from '@/lib/utils'
import { useColor } from '@/lib/color-context'

export function FundDetail() {
  const navigate = useNavigate()
  const { code } = useParams<{ code: string }>()
  const { colorFor } = useColor()
  const { selectedId } = useSelectedPortfolio()

  const detailQ = useFundDetail(code)
  const { data: history = [], isLoading: navLoading } = useNavHistory(code, 500)
  const { data: holdings = [] } = useFundHoldings(code)
  const { data: quote } = useQuote(code)
  const { data: transactions = [] } = useTransactions(code, selectedId)
  const addFund = useAddFund(selectedId)

  const [addMsg, setAddMsg] = useState<{ text: string; ok: boolean } | null>(null)
  const [showAddTx, setShowAddTx] = useState(false)

  const detail = detailQ.data
  const loading = detailQ.isLoading || navLoading
  const notFound = detailQ.isError

  const navValue = quote?.gsz ?? (history.length > 0 ? history[history.length - 1].nav : null)
  const changeValue = quote?.gszzl ?? null

  function handleAddFund() {
    if (!code) return
    addFund.mutate(code, {
      onSuccess: () => setAddMsg({ text: '已加入自选', ok: true }),
      onError: () => setAddMsg({ text: '加入失败', ok: false }),
      onSettled: () => setTimeout(() => setAddMsg(null), 3000),
    })
  }

  /* ---- loading / not found ---- */
  if (loading) {
    return <PageState loading className="h-[60vh] py-0" />
  }

  if (notFound || !detail) {
    return (
      <PageState
        error
        className="h-[60vh] py-0 flex-col text-center"
        errorContent={
          <>
            <p className="text-xl text-slate-500 mb-4">未找到该基金</p>
            <button onClick={() => navigate(-1)} className="text-blue-600 hover:underline flex items-center gap-1">
              <ArrowLeft className="h-4 w-4" /> 返回基金列表
            </button>
          </>
        }
      />
    )
  }

  return (
    <div className="space-y-6">
      <HoldingEditModal
        open={showAddTx}
        onClose={() => setShowAddTx(false)}
        code={code!}
        name={detail.name}
        defaultNav={quote?.gsz ?? (history.length > 0 ? history[history.length - 1].nav : undefined)}
        portfolioId={selectedId}
      />

      {/* ---- Top bar ---- */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => navigate(-1)}
          className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-blue-600 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" /> 返回
        </button>
        <div className="flex items-center gap-2">
          <button
            onClick={handleAddFund}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors"
          >
            <Plus className="h-4 w-4" /> 加入自选
          </button>
          {addMsg && (
            <span className={cn('text-sm font-medium', addMsg.ok ? 'text-green-600' : 'text-red-600')}>
              {addMsg.text}
            </span>
          )}
        </div>
      </div>

      {/* ---- Header card ---- */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {/* blue gradient top line */}
        <div className="h-1 bg-gradient-to-r from-blue-500 to-blue-300" />
        <div className="p-6 flex flex-col md:flex-row md:items-start md:justify-between gap-4">
          {/* left: fund info */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              {detail.fund_type && (
                <span className="inline-block px-2 py-0.5 text-xs font-medium rounded bg-blue-100 text-blue-700">
                  {detail.fund_type}
                </span>
              )}
              <span className="inline-block px-2 py-0.5 text-xs font-medium rounded bg-slate-100 text-slate-500">
                {detail.code}
              </span>
            </div>
            <h1 className="text-3xl font-bold text-slate-900 mb-3">
              {detail.name || detail.code}
            </h1>
            <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-slate-500">
              {detail.manager && (
                <span>基金经理: <span className="text-slate-700">{detail.manager}</span></span>
              )}
              {detail.size != null && (
                <span>规模: <span className="text-slate-700">{detail.size >= 1 ? `${detail.size.toFixed(2)}亿` : `${(detail.size * 10000).toFixed(0)}万`}</span></span>
              )}
              {detail.established_date && (
                <span>成立日期: <span className="text-slate-700">{detail.established_date}</span></span>
              )}
            </div>
          </div>

          {/* right: NAV display */}
          <div className="text-right md:min-w-[180px]">
            <p className="text-xs text-slate-400 mb-1 flex items-center justify-end gap-1">
              单位净值(估)
              {quote?.gztime && (
                <span
                  className="inline-flex items-center px-1 rounded bg-blue-50 text-blue-600 border border-blue-200 text-[10px] leading-4 cursor-help"
                  title={`盘中估算值 · ${quote.gztime}`}
                >
                  估
                </span>
              )}
            </p>
            <p className="text-4xl font-bold text-slate-900">
              {navValue != null ? navValue.toFixed(4) : '--'}
            </p>
            {changeValue != null && (
              <p className={cn('text-lg font-semibold mt-1', colorFor(changeValue))}>
                {formatPercent(changeValue)}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* ---- Main content: left 2/3 + right 1/3 ---- */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column */}
        <div className="lg:col-span-2 space-y-6">
          <NavChart history={history} transactions={transactions} />
          <StageReturns detail={detail} />
          <RiskMetrics history={history} detail={detail} />
        </div>

        {/* Right column */}
        <div className="space-y-6">
          <SignalGauge history={history} />
          <AssetAllocationCard detail={detail} />
          <TopHoldings holdings={holdings} />
        </div>
      </div>

      <TransactionsCard transactions={transactions} onAddTx={() => setShowAddTx(true)} />
    </div>
  )
}
