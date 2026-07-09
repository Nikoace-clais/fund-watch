import { useCallback, useMemo, useState } from 'react'
import { PieChart as PieChartIcon, Plus } from 'lucide-react'
import { AddFundModal } from '@/components/AddFundModal'
import { HoldingEditModal } from '@/components/HoldingEditModal'
import { PageState } from '@/components/PageState'
import { StatsCards } from '@/components/portfolio/StatsCards'
import { TrendChart } from '@/components/portfolio/TrendChart'
import { AllocationPie } from '@/components/portfolio/AllocationPie'
import { HoldingsTable } from '@/components/portfolio/HoldingsTable'
import { HoldingsXray } from '@/components/portfolio/HoldingsXray'
import {
  WatchTable,
  type WatchOnlyItem,
} from '@/components/portfolio/WatchTable'
import { TransactionModal } from '@/components/portfolio/TransactionModal'
import { PortfolioSwitcher } from '@/components/portfolio/PortfolioSwitcher'
import {
  useDeleteFund,
  useFundsOverview,
  usePortfolioHoldings,
  usePortfolioSummary,
} from '@/lib/queries'
import { useSelectedPortfolio } from '@/lib/portfolio-context'

export function Portfolio() {
  const { portfolios, selectedId } = useSelectedPortfolio()
  const { data: summary, isLoading: summaryLoading } =
    usePortfolioSummary(selectedId)
  const { data: overview = [], isLoading: overviewLoading } = useFundsOverview()
  const { data: portfolioHoldings } = usePortfolioHoldings(selectedId)
  const deleteFund = useDeleteFund(selectedId)

  const [batchDeleting, setBatchDeleting] = useState(false)
  const [showAddModal, setShowAddModal] = useState(false)
  const [holdingEdit, setHoldingEdit] = useState<{
    code: string
    name?: string
    nav?: number
  } | null>(null)
  const [txView, setTxView] = useState<{ code: string; name?: string } | null>(
    null,
  )

  const loading = summaryLoading || overviewLoading
  const items = summary?.items ?? []

  const watchOnly = useMemo<WatchOnlyItem[]>(() => {
    const watchCodes = new Set(summary?.watch_codes ?? [])
    return overview
      .filter((i) => watchCodes.has(i.fund.code))
      .map((i) => ({
        code: i.fund.code,
        name: i.latest?.name || i.fund.name,
        gszzl: i.latest?.gszzl,
        gsz: i.latest?.gsz ?? i.latest?.dwjz,
      }))
  }, [summary, overview])

  // Single-delete: both the holdings table and the watch-only table scope to
  // the current portfolio — genuinely the same handler.
  const handleDeleteFund = useCallback(
    (code: string, name?: string) => {
      if (!confirm(`确认删除基金 ${name || code}?`)) return
      deleteFund.mutate({ code, scopeToPortfolio: selectedId })
    },
    [deleteFund, selectedId],
  )

  // Batch delete: holdings scope to the current portfolio; watch-only batch
  // delete removes the fund globally — preserved from the original behavior.
  const runBatchDelete = useCallback(
    async (
      codes: string[],
      clearSelection: () => void,
      scopeToPortfolio: number | undefined,
    ) => {
      if (!confirm(`确认删除选中的 ${codes.length} 只基金？此操作不可撤销。`))
        return
      setBatchDeleting(true)
      try {
        const results = await Promise.allSettled(
          codes.map((code) =>
            deleteFund.mutateAsync({ code, scopeToPortfolio }),
          ),
        )
        const failed = results.filter((r) => r.status === 'rejected').length
        if (failed > 0) {
          alert(`${failed} 只基金删除失败，请稍后重试`)
        } else {
          clearSelection()
        }
      } finally {
        setBatchDeleting(false)
      }
    },
    [deleteFund],
  )
  const handleBatchDeleteHolding = useCallback(
    (codes: string[], clearSelection: () => void) =>
      runBatchDelete(codes, clearSelection, selectedId),
    [runBatchDelete, selectedId],
  )
  const handleBatchDeleteWatch = useCallback(
    (codes: string[], clearSelection: () => void) =>
      runBatchDelete(codes, clearSelection, undefined),
    [runBatchDelete],
  )

  // deleteFund is shared by single-row delete and the batch-delete loop below;
  // while a batch is running its .isPending/.variables reflect an arbitrary
  // in-flight code, not the row the user actually clicked — suppress it then.
  const deleting =
    !batchDeleting && deleteFund.isPending
      ? (deleteFund.variables?.code ?? null)
      : null

  const handleEditHolding = useCallback(
    (h: { code: string; name?: string; nav?: number }) => setHoldingEdit(h),
    [],
  )
  const handleViewTx = useCallback(
    (code: string, name?: string) => setTxView({ code, name }),
    [],
  )

  const totalCurrent = parseFloat(summary?.total_current ?? '0')
  const totalCost = parseFloat(summary?.total_cost ?? '0')
  const hasItems = items.length > 0

  if (loading) {
    return <PageState loading />
  }

  return (
    <div className="space-y-8">
      {/* ---- Header ---- */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">自选基金与持仓</h1>
          <p className="text-sm text-slate-500 mt-1">
            管理你的基金组合与持仓情况
          </p>
        </div>
        <div className="flex items-center gap-2">
          <PortfolioSwitcher />

          <button
            onClick={() => setShowAddModal(true)}
            className="inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 transition-colors shadow-sm"
          >
            <Plus className="h-4 w-4" />
            添加基金
          </button>
        </div>
      </div>

      <AddFundModal
        open={showAddModal}
        onClose={() => setShowAddModal(false)}
        portfolioId={selectedId}
        existingCodes={overview.map((i) => i.fund.code)}
      />
      <HoldingEditModal
        open={holdingEdit !== null}
        onClose={() => setHoldingEdit(null)}
        code={holdingEdit?.code ?? ''}
        name={holdingEdit?.name}
        defaultNav={holdingEdit?.nav}
        portfolioId={selectedId}
      />

      {txView && (
        <TransactionModal
          code={txView.code}
          name={txView.name}
          portfolioId={selectedId}
          onClose={() => setTxView(null)}
          onAddTx={() => {
            setTxView(null)
            setHoldingEdit({ code: txView.code, name: txView.name })
          }}
        />
      )}

      {/* ---- Empty state (no portfolios at all) ---- */}
      {portfolios.length === 0 && (
        <div className="flex flex-col items-center justify-center py-32 text-center">
          <div className="rounded-full bg-slate-100 p-6 mb-6">
            <PieChartIcon className="h-10 w-10 text-slate-400" />
          </div>
          <h2 className="text-xl font-semibold text-slate-700 mb-2">
            暂无组合
          </h2>
          <p className="text-sm text-slate-400 mb-6">
            通过截图导入创建第一个组合，或在上方点击「选择组合」新建
          </p>
        </div>
      )}

      {/* ---- Empty state (portfolio exists but no holdings) ---- */}
      {portfolios.length > 0 && !hasItems && watchOnly.length === 0 && (
        <div className="flex flex-col items-center justify-center py-32 text-center">
          <div className="rounded-full bg-slate-100 p-6 mb-6">
            <PieChartIcon className="h-10 w-10 text-slate-400" />
          </div>
          <h2 className="text-xl font-semibold text-slate-700 mb-2">
            暂无持仓
          </h2>
          <p className="text-sm text-slate-400 mb-6">
            点击上方「添加基金」按钮，通过搜索、输入代码或截图导入添加基金
          </p>
          <button
            onClick={() => setShowAddModal(true)}
            className="inline-flex items-center gap-1.5 text-blue-600 hover:text-blue-700 font-medium text-sm"
          >
            <Plus className="h-4 w-4" /> 立即添加
          </button>
        </div>
      )}

      {/* ---- Stats + trend + holdings ---- */}
      {hasItems && summary && (
        <>
          <StatsCards summary={summary} />
          <TrendChart totalCost={totalCost} portfolioId={selectedId} />

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            <HoldingsTable
              items={items}
              totalCurrent={totalCurrent}
              deleting={deleting}
              batchDeleting={batchDeleting}
              onViewTx={handleViewTx}
              onEditHolding={handleEditHolding}
              onDelete={handleDeleteFund}
              onBatchDelete={handleBatchDeleteHolding}
            />
            <AllocationPie
              items={items}
              totalCurrent={totalCurrent}
              fundCount={summary.fund_count}
            />
          </div>

          {portfolioHoldings && portfolioHoldings.stocks.length > 0 && (
            <HoldingsXray data={portfolioHoldings} />
          )}
        </>
      )}

      {/* ---- Watch-only table ---- */}
      {watchOnly.length > 0 && (
        <WatchTable
          items={watchOnly}
          deleting={deleting}
          batchDeleting={batchDeleting}
          onEditHolding={handleEditHolding}
          onDelete={handleDeleteFund}
          onBatchDelete={handleBatchDeleteWatch}
        />
      )}
    </div>
  )
}
