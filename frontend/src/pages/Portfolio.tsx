import { useCallback, useMemo, useState } from 'react'
import { PieChart as PieChartIcon, Plus } from 'lucide-react'
import { AddFundModal } from '@/components/AddFundModal'
import { HoldingEditModal } from '@/components/HoldingEditModal'
import { PageState } from '@/components/PageState'
import { StatsCards } from '@/components/portfolio/StatsCards'
import { TrendChart } from '@/components/portfolio/TrendChart'
import { AllocationPie } from '@/components/portfolio/AllocationPie'
import { HoldingsTable } from '@/components/portfolio/HoldingsTable'
import { WatchTable, type WatchOnlyItem } from '@/components/portfolio/WatchTable'
import { TransactionModal } from '@/components/portfolio/TransactionModal'
import { deleteFund } from '@/lib/api'
import { useFundsOverview, useInvalidatePortfolio, usePortfolioSummary } from '@/lib/queries'

export function Portfolio() {
  const { data: summary, isLoading: summaryLoading } = usePortfolioSummary()
  const { data: overview = [], isLoading: overviewLoading } = useFundsOverview()
  const invalidatePortfolio = useInvalidatePortfolio()

  const [deleting, setDeleting] = useState<string | null>(null)
  const [batchDeleting, setBatchDeleting] = useState(false)
  const [showAddModal, setShowAddModal] = useState(false)
  const [holdingEdit, setHoldingEdit] = useState<{ code: string; name?: string; nav?: number } | null>(null)
  const [txView, setTxView] = useState<{ code: string; name?: string } | null>(null)

  const loading = summaryLoading || overviewLoading
  const items = summary?.items ?? []

  /* 自选但未持仓的基金 */
  const watchOnly = useMemo<WatchOnlyItem[]>(() => {
    const holdingCodes = new Set(items.map((i) => i.code))
    return overview
      .filter((i) => !holdingCodes.has(i.fund.code))
      .map((i) => ({
        code: i.fund.code,
        name: i.latest?.name || i.fund.name,
        gszzl: i.latest?.gszzl,
        gsz: i.latest?.gsz ?? i.latest?.dwjz,
      }))
  }, [items, overview])

  const handleDelete = useCallback(
    async (code: string, name?: string) => {
      if (!confirm(`确认删除基金 ${name || code}?`)) return
      setDeleting(code)
      try {
        await deleteFund(code)
        invalidatePortfolio()
      } finally {
        setDeleting(null)
      }
    },
    [invalidatePortfolio],
  )

  const handleBatchDelete = useCallback(
    async (codes: string[], clearSelection: () => void) => {
      if (!confirm(`确认删除选中的 ${codes.length} 只基金？此操作不可撤销。`)) return
      setBatchDeleting(true)
      try {
        const results = await Promise.allSettled(codes.map((c) => deleteFund(c)))
        invalidatePortfolio()
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
    [invalidatePortfolio],
  )

  const handleEditHolding = useCallback(
    (h: { code: string; name?: string; nav?: number }) => setHoldingEdit(h),
    [],
  )
  const handleViewTx = useCallback(
    (code: string, name?: string) => setTxView({ code, name }),
    [],
  )

  /* derived */
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
          <p className="text-sm text-slate-500 mt-1">管理你的基金组合与持仓情况</p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 transition-colors shadow-sm"
        >
          <Plus className="h-4 w-4" />
          添加基金
        </button>
      </div>

      <AddFundModal
        open={showAddModal}
        onClose={() => setShowAddModal(false)}
        onAdded={invalidatePortfolio}
        existingCodes={overview.map((i) => i.fund.code)}
      />
      <HoldingEditModal
        open={holdingEdit !== null}
        onClose={() => setHoldingEdit(null)}
        onSaved={invalidatePortfolio}
        code={holdingEdit?.code ?? ''}
        name={holdingEdit?.name}
        defaultNav={holdingEdit?.nav}
      />

      {txView && (
        <TransactionModal
          code={txView.code}
          name={txView.name}
          onClose={() => setTxView(null)}
          onAddTx={() => { setTxView(null); setHoldingEdit({ code: txView.code, name: txView.name }) }}
        />
      )}

      {/* ---- Empty state ---- */}
      {!hasItems && watchOnly.length === 0 && (
        <div className="flex flex-col items-center justify-center py-32 text-center">
          <div className="rounded-full bg-slate-100 p-6 mb-6">
            <PieChartIcon className="h-10 w-10 text-slate-400" />
          </div>
          <h2 className="text-xl font-semibold text-slate-700 mb-2">暂无自选基金</h2>
          <p className="text-sm text-slate-400 mb-6">点击上方"添加基金"按钮，通过搜索、输入代码或批量导入添加基金</p>
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
          <TrendChart totalCost={totalCost} />

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            <HoldingsTable
              items={items}
              totalCurrent={totalCurrent}
              deleting={deleting}
              batchDeleting={batchDeleting}
              onViewTx={handleViewTx}
              onEditHolding={handleEditHolding}
              onDelete={handleDelete}
              onBatchDelete={handleBatchDelete}
            />
            <AllocationPie items={items} totalCurrent={totalCurrent} fundCount={summary.fund_count} />
          </div>
        </>
      )}

      {/* ---- Watch-only table ---- */}
      {watchOnly.length > 0 && (
        <WatchTable
          items={watchOnly}
          deleting={deleting}
          batchDeleting={batchDeleting}
          onEditHolding={handleEditHolding}
          onDelete={handleDelete}
          onBatchDelete={handleBatchDelete}
        />
      )}
    </div>
  )
}
