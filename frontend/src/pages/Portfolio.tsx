import { useCallback, useMemo, useState } from 'react'
import { PieChart as PieChartIcon, Plus, ChevronDown, Trash2, Pencil } from 'lucide-react'
import { AddFundModal } from '@/components/AddFundModal'
import { HoldingEditModal } from '@/components/HoldingEditModal'
import { PageState } from '@/components/PageState'
import { StatsCards } from '@/components/portfolio/StatsCards'
import { TrendChart } from '@/components/portfolio/TrendChart'
import { AllocationPie } from '@/components/portfolio/AllocationPie'
import { HoldingsTable } from '@/components/portfolio/HoldingsTable'
import { HoldingsXray } from '@/components/portfolio/HoldingsXray'
import { WatchTable, type WatchOnlyItem } from '@/components/portfolio/WatchTable'
import { TransactionModal } from '@/components/portfolio/TransactionModal'
import { deleteFund, createPortfolio, renamePortfolio, deletePortfolio } from '@/lib/api'
import {
  useFundsOverview,
  useInvalidatePortfolio,
  usePortfolioHoldings,
  usePortfolioSummary,
  usePortfolios,
} from '@/lib/queries'
import { useQueryClient } from '@tanstack/react-query'
import { keys } from '@/lib/queries'

// ponytail: localStorage for portfolio selection — good enough for single-user MVP
const STORAGE_KEY = 'fw_portfolio_id'

function useSelectedPortfolio() {
  const { data: portfolios = [] } = usePortfolios()
  const [rawId, setRawId] = useState<number | null>(() => {
    const v = localStorage.getItem(STORAGE_KEY)
    return v ? parseInt(v, 10) : null
  })

  // Derive the effective ID: use stored if it still exists, else first portfolio
  const effectiveId = useMemo(() => {
    if (!portfolios.length) return undefined
    if (rawId != null && portfolios.some((p) => p.id === rawId)) return rawId
    return portfolios[0].id
  }, [portfolios, rawId])

  const selectPortfolio = useCallback((id: number) => {
    localStorage.setItem(STORAGE_KEY, String(id))
    setRawId(id)
  }, [])

  return { portfolios, selectedId: effectiveId, selectPortfolio }
}

export function Portfolio() {
  const { portfolios, selectedId, selectPortfolio } = useSelectedPortfolio()
  const { data: summary, isLoading: summaryLoading } = usePortfolioSummary(selectedId)
  const { data: overview = [], isLoading: overviewLoading } = useFundsOverview()
  const { data: portfolioHoldings } = usePortfolioHoldings(selectedId)
  const invalidatePortfolio = useInvalidatePortfolio(selectedId)
  const qc = useQueryClient()

  const [deleting, setDeleting] = useState<string | null>(null)
  const [batchDeleting, setBatchDeleting] = useState(false)
  const [showAddModal, setShowAddModal] = useState(false)
  const [holdingEdit, setHoldingEdit] = useState<{ code: string; name?: string; nav?: number } | null>(null)
  const [txView, setTxView] = useState<{ code: string; name?: string } | null>(null)
  const [pfMenuOpen, setPfMenuOpen] = useState(false)
  const [renamingId, setRenamingId] = useState<number | null>(null)
  const [renameName, setRenameName] = useState('')
  const [newPfName, setNewPfName] = useState('')
  const [showNewPfInput, setShowNewPfInput] = useState(false)

  const loading = summaryLoading || overviewLoading
  const items = summary?.items ?? []
  const currentPortfolio = portfolios.find((p) => p.id === selectedId)

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

  const handleDeleteHolding = useCallback(
    async (code: string, name?: string) => {
      if (!confirm(`确认删除基金 ${name || code}?`)) return
      setDeleting(code)
      try {
        await deleteFund(code, selectedId)
        invalidatePortfolio()
      } finally {
        setDeleting(null)
      }
    },
    [invalidatePortfolio, selectedId],
  )

  const handleBatchDeleteHolding = useCallback(
    async (codes: string[], clearSelection: () => void) => {
      if (!confirm(`确认删除选中的 ${codes.length} 只基金？此操作不可撤销。`)) return
      setBatchDeleting(true)
      try {
        const results = await Promise.allSettled(codes.map((c) => deleteFund(c, selectedId)))
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
    [invalidatePortfolio, selectedId],
  )

  const handleDeleteWatch = useCallback(
    async (code: string, name?: string) => {
      if (!confirm(`确认删除基金 ${name || code}?`)) return
      setDeleting(code)
      try {
        await deleteFund(code, selectedId)
        invalidatePortfolio()
      } finally {
        setDeleting(null)
      }
    },
    [invalidatePortfolio, selectedId],
  )

  const handleBatchDeleteWatch = useCallback(
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

  const handleCreatePortfolio = async () => {
    const name = newPfName.trim()
    if (!name) return
    const res = await createPortfolio(name)
    qc.invalidateQueries({ queryKey: keys.portfolios })
    selectPortfolio(res.id)
    setNewPfName('')
    setShowNewPfInput(false)
    setPfMenuOpen(false)
  }

  const handleRenamePortfolio = async () => {
    if (!renamingId || !renameName.trim()) return
    await renamePortfolio(renamingId, renameName.trim())
    qc.invalidateQueries({ queryKey: keys.portfolios })
    setRenamingId(null)
    setRenameName('')
  }

  const handleDeletePortfolio = async (id: number, name: string) => {
    if (!confirm(`确认删除组合「${name}」？该组合的所有持仓和交易记录将被清除，基金仍保留在自选列表中。`)) return
    await deletePortfolio(id)
    qc.invalidateQueries({ queryKey: keys.portfolios })
    // Switch to first remaining portfolio
    const remaining = portfolios.filter((p) => p.id !== id)
    if (remaining.length > 0) selectPortfolio(remaining[0].id)
    setPfMenuOpen(false)
  }

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
        <div className="flex items-center gap-2">
          {/* Portfolio selector */}
          {portfolios.length > 0 && (
            <div className="relative">
              <button
                onClick={() => setPfMenuOpen((v) => !v)}
                className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition-colors shadow-sm"
              >
                <span className="max-w-[140px] truncate">{currentPortfolio?.name ?? '选择组合'}</span>
                <ChevronDown className="h-4 w-4 text-slate-400 flex-shrink-0" />
              </button>
              {pfMenuOpen && (
                <div className="absolute right-0 mt-1 w-64 bg-white rounded-xl shadow-lg border border-slate-200 z-20 py-1">
                  {portfolios.map((pf) => (
                    <div
                      key={pf.id}
                      className={`flex items-center gap-2 px-3 py-2 text-sm cursor-pointer ${pf.id === selectedId ? 'bg-blue-50 text-blue-700' : 'text-slate-700 hover:bg-slate-50'}`}
                    >
                      {renamingId === pf.id ? (
                        <form
                          className="flex-1 flex gap-1"
                          onSubmit={(e) => { e.preventDefault(); handleRenamePortfolio() }}
                        >
                          <input
                            autoFocus
                            value={renameName}
                            onChange={(e) => setRenameName(e.target.value)}
                            className="flex-1 border border-blue-300 rounded px-1.5 py-0.5 text-xs outline-none"
                          />
                          <button type="submit" className="text-blue-600 text-xs font-medium">确认</button>
                          <button type="button" onClick={() => setRenamingId(null)} className="text-slate-400 text-xs">取消</button>
                        </form>
                      ) : (
                        <>
                          <span
                            className="flex-1 truncate"
                            onClick={() => { selectPortfolio(pf.id); setPfMenuOpen(false) }}
                          >
                            {pf.name}
                            <span className="ml-1 text-xs text-slate-400">({pf.fund_count})</span>
                          </span>
                          <button
                            onClick={() => { setRenamingId(pf.id); setRenameName(pf.name) }}
                            className="text-slate-400 hover:text-slate-600 flex-shrink-0"
                            title="重命名"
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </button>
                          {portfolios.length > 1 && (
                            <button
                              onClick={() => handleDeletePortfolio(pf.id, pf.name)}
                              className="text-slate-400 hover:text-red-500 flex-shrink-0"
                              title="删除组合"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          )}
                        </>
                      )}
                    </div>
                  ))}
                  <div className="border-t border-slate-100 mt-1 pt-1 px-3 pb-1">
                    {showNewPfInput ? (
                      <form
                        className="flex gap-1.5"
                        onSubmit={(e) => { e.preventDefault(); handleCreatePortfolio() }}
                      >
                        <input
                          autoFocus
                          value={newPfName}
                          onChange={(e) => setNewPfName(e.target.value)}
                          placeholder="组合名称"
                          className="flex-1 border border-blue-300 rounded px-2 py-1 text-xs outline-none"
                        />
                        <button type="submit" className="text-blue-600 text-xs font-medium">创建</button>
                        <button type="button" onClick={() => setShowNewPfInput(false)} className="text-slate-400 text-xs">取消</button>
                      </form>
                    ) : (
                      <button
                        onClick={() => setShowNewPfInput(true)}
                        className="w-full text-left text-xs text-blue-600 hover:text-blue-700 py-1 flex items-center gap-1"
                      >
                        <Plus className="h-3.5 w-3.5" /> 新建组合
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

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
        portfolioId={selectedId}
      />

      {txView && (
        <TransactionModal
          code={txView.code}
          name={txView.name}
          portfolioId={selectedId}
          onClose={() => setTxView(null)}
          onAddTx={() => { setTxView(null); setHoldingEdit({ code: txView.code, name: txView.name }) }}
        />
      )}

      {/* ---- Empty state (no portfolios at all) ---- */}
      {portfolios.length === 0 && (
        <div className="flex flex-col items-center justify-center py-32 text-center">
          <div className="rounded-full bg-slate-100 p-6 mb-6">
            <PieChartIcon className="h-10 w-10 text-slate-400" />
          </div>
          <h2 className="text-xl font-semibold text-slate-700 mb-2">暂无组合</h2>
          <p className="text-sm text-slate-400 mb-6">通过截图导入创建第一个组合，或在上方点击「选择组合」新建</p>
        </div>
      )}

      {/* ---- Empty state (portfolio exists but no holdings) ---- */}
      {portfolios.length > 0 && !hasItems && watchOnly.length === 0 && (
        <div className="flex flex-col items-center justify-center py-32 text-center">
          <div className="rounded-full bg-slate-100 p-6 mb-6">
            <PieChartIcon className="h-10 w-10 text-slate-400" />
          </div>
          <h2 className="text-xl font-semibold text-slate-700 mb-2">暂无持仓</h2>
          <p className="text-sm text-slate-400 mb-6">点击上方「添加基金」按钮，通过搜索、输入代码或截图导入添加基金</p>
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
              onDelete={handleDeleteHolding}
              onBatchDelete={handleBatchDeleteHolding}
            />
            <AllocationPie items={items} totalCurrent={totalCurrent} fundCount={summary.fund_count} />
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
          onDelete={handleDeleteWatch}
          onBatchDelete={handleBatchDeleteWatch}
        />
      )}
    </div>
  )
}
