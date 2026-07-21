import { useRef, useState } from 'react'
import { ChevronDown, Trash2, Pencil, Plus } from 'lucide-react'
import {
  useCreatePortfolio,
  useDeletePortfolio,
  useRenamePortfolio,
} from '@/lib/queries'
import { useClickOutside } from '@/lib/hooks'
import { useSelectedPortfolio } from '@/lib/portfolio-context'

export function PortfolioSwitcher() {
  const { portfolios, selectedId, selectPortfolio } = useSelectedPortfolio()
  const createPortfolio = useCreatePortfolio()
  const renamePortfolio = useRenamePortfolio()
  const deletePortfolio = useDeletePortfolio()

  const [pfMenuOpen, setPfMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  useClickOutside(menuRef, pfMenuOpen, () => setPfMenuOpen(false))
  const [renamingId, setRenamingId] = useState<number | null>(null)
  const [renameName, setRenameName] = useState('')
  const [newPfName, setNewPfName] = useState('')
  const [showNewPfInput, setShowNewPfInput] = useState(false)

  const currentPortfolio = portfolios.find((p) => p.id === selectedId)

  const handleCreatePortfolio = async () => {
    const name = newPfName.trim()
    if (!name) return
    const res = await createPortfolio.mutateAsync(name)
    selectPortfolio(res.id)
    setNewPfName('')
    setShowNewPfInput(false)
    setPfMenuOpen(false)
  }

  const handleRenamePortfolio = async () => {
    if (!renamingId || !renameName.trim()) return
    await renamePortfolio.mutateAsync({
      id: renamingId,
      name: renameName.trim(),
    })
    setRenamingId(null)
    setRenameName('')
  }

  const handleDeletePortfolio = async (id: number, name: string) => {
    if (
      !confirm(
        `确认删除组合「${name}」？该组合的所有持仓和交易记录将被清除，基金仍保留在自选列表中。`,
      )
    )
      return
    await deletePortfolio.mutateAsync(id)
    // Switch to first remaining portfolio
    const remaining = portfolios.filter((p) => p.id !== id)
    if (remaining.length > 0) selectPortfolio(remaining[0].id)
    setPfMenuOpen(false)
  }

  if (portfolios.length === 0) return null

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setPfMenuOpen((v) => !v)}
        className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition-colors shadow-sm"
      >
        <span className="max-w-[140px] truncate">
          {currentPortfolio?.name ?? '选择组合'}
        </span>
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
                  onSubmit={(e) => {
                    e.preventDefault()
                    handleRenamePortfolio()
                  }}
                >
                  <input
                    autoFocus
                    value={renameName}
                    onChange={(e) => setRenameName(e.target.value)}
                    className="flex-1 border border-blue-300 rounded px-1.5 py-0.5 text-xs outline-none"
                  />
                  <button
                    type="submit"
                    className="text-blue-600 text-xs font-medium"
                  >
                    确认
                  </button>
                  <button
                    type="button"
                    onClick={() => setRenamingId(null)}
                    className="text-slate-400 text-xs"
                  >
                    取消
                  </button>
                </form>
              ) : (
                <>
                  <span
                    className="flex-1 truncate"
                    onClick={() => {
                      selectPortfolio(pf.id)
                      setPfMenuOpen(false)
                    }}
                  >
                    {pf.name}
                    <span className="ml-1 text-xs text-slate-400">
                      ({pf.fund_count})
                    </span>
                  </span>
                  <button
                    onClick={() => {
                      setRenamingId(pf.id)
                      setRenameName(pf.name)
                    }}
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
                onSubmit={(e) => {
                  e.preventDefault()
                  handleCreatePortfolio()
                }}
              >
                <input
                  autoFocus
                  value={newPfName}
                  onChange={(e) => setNewPfName(e.target.value)}
                  placeholder="组合名称"
                  className="flex-1 border border-blue-300 rounded px-2 py-1 text-xs outline-none"
                />
                <button
                  type="submit"
                  className="text-blue-600 text-xs font-medium"
                >
                  创建
                </button>
                <button
                  type="button"
                  onClick={() => setShowNewPfInput(false)}
                  className="text-slate-400 text-xs"
                >
                  取消
                </button>
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
  )
}
