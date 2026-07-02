import { Plus, Trash2, X } from 'lucide-react'
import { useDeleteTransaction, useTransactions } from '@/lib/queries'
import { cn, formatCNY } from '@/lib/utils'

export function TransactionModal({
  code, name, portfolioId, onClose, onAddTx,
}: {
  code: string
  name?: string
  portfolioId?: number
  onClose: () => void
  onAddTx: () => void
}) {
  const { data: items = [], isLoading: loading } = useTransactions(code, portfolioId)
  const deleteTransaction = useDeleteTransaction(portfolioId)

  const handleDelete = (id: number) => {
    if (!confirm('确认删除该条交易记录？')) return
    deleteTransaction.mutate(id, {
      onError: (err: Error) => alert(err.message || '删除失败'),
    })
  }
  const deleting = deleteTransaction.isPending ? (deleteTransaction.variables ?? null) : null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 flex flex-col max-h-[80vh]">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 shrink-0">
          <div>
            <h2 className="text-base font-semibold text-slate-900">交易记录</h2>
            <p className="text-xs text-slate-400 mt-0.5">{name || code} · {code}</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={onAddTx}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-500 text-white text-sm hover:bg-blue-600 transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              记录交易
            </button>
            <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 transition-colors">
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        <div className="overflow-y-auto flex-1 px-6 py-4">
          {loading ? (
            <p className="text-center text-slate-400 py-8 text-sm">加载中...</p>
          ) : items.length === 0 ? (
            <p className="text-center text-slate-400 py-8 text-sm">暂无交易记录</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-slate-400 border-b border-slate-100">
                  <th className="text-left pb-2 font-medium">日期</th>
                  <th className="text-center pb-2 font-medium">方向</th>
                  <th className="text-right pb-2 font-medium">净值</th>
                  <th className="text-right pb-2 font-medium">份额</th>
                  <th className="text-right pb-2 font-medium">金额</th>
                  <th className="text-center pb-2 font-medium">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {items.map((tx) => (
                  <tr key={tx.id} className="hover:bg-slate-50">
                    <td className="py-2.5 text-slate-600">{tx.trade_date}</td>
                    <td className="py-2.5 text-center">
                      <span className={cn(
                        'inline-block px-2 py-0.5 rounded-full text-xs font-medium',
                        tx.direction === 'buy' ? 'bg-red-50 text-red-600' : 'bg-green-50 text-green-600',
                      )}>
                        {tx.direction === 'buy' ? '买入' : '卖出'}
                      </span>
                    </td>
                    <td className="py-2.5 text-right text-slate-700">{parseFloat(tx.nav).toFixed(4)}</td>
                    <td className="py-2.5 text-right text-slate-700">{parseFloat(tx.shares).toFixed(2)}</td>
                    <td className="py-2.5 text-right text-slate-700">{formatCNY(parseFloat(tx.amount))}</td>
                    <td className="py-2.5 text-center">
                      <button
                        onClick={() => handleDelete(tx.id)}
                        disabled={deleting === tx.id}
                        className="p-1 rounded text-slate-300 hover:text-red-500 hover:bg-red-50 transition-colors disabled:opacity-50"
                        title="删除"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
