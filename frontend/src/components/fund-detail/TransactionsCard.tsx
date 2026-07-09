import { Plus, Trash2, TrendingUp } from 'lucide-react'
import { type Transaction } from '@/lib/api'
import { useDeleteTxConfirm } from '@/lib/queries'
import { useSelectedPortfolio } from '@/lib/portfolio-context'
import { cn, formatCNY } from '@/lib/utils'

export function TransactionsCard({
  transactions,
  onAddTx,
}: {
  transactions: Transaction[]
  onAddTx: () => void
}) {
  const { selectedId } = useSelectedPortfolio()
  const { handleDelete: handleDeleteTx, deletingId: deletingTx } =
    useDeleteTxConfirm(selectedId)

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
      <div className="flex items-center gap-2 mb-4">
        <TrendingUp className="h-5 w-5 text-slate-600" />
        <h2 className="text-lg font-semibold text-slate-800">买卖明细</h2>
        <span className="text-xs text-slate-400">{transactions.length} 笔</span>
        <button
          onClick={onAddTx}
          className="ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-500 text-white text-sm hover:bg-blue-600 transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />
          记录交易
        </button>
      </div>

      {transactions.length === 0 ? (
        <div className="flex items-center justify-center h-24 text-slate-400 text-sm">
          暂无交易记录
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-slate-400 border-b border-slate-100">
                <th className="text-left pb-2 font-medium">日期</th>
                <th className="text-left pb-2 font-medium">方向</th>
                <th className="text-right pb-2 font-medium">成交净值</th>
                <th className="text-right pb-2 font-medium">份额</th>
                <th className="text-right pb-2 font-medium">金额</th>
                <th className="text-right pb-2 font-medium">手续费</th>
                <th className="text-left pb-2 font-medium pl-4">备注</th>
                <th className="text-center pb-2 font-medium">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {transactions.map((tx) => (
                <tr key={tx.id} className="hover:bg-slate-50 transition-colors">
                  <td className="py-2.5 text-slate-600">{tx.trade_date}</td>
                  <td className="py-2.5">
                    <span
                      className={cn(
                        'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                        tx.direction === 'buy'
                          ? 'bg-red-50 text-red-600'
                          : 'bg-green-50 text-green-600',
                      )}
                    >
                      {tx.direction === 'buy' ? '买入' : '卖出'}
                    </span>
                  </td>
                  <td className="py-2.5 text-right text-slate-700 font-mono">
                    {parseFloat(tx.nav).toFixed(4)}
                  </td>
                  <td className="py-2.5 text-right text-slate-700">
                    {parseFloat(tx.shares).toLocaleString('zh-CN', {
                      maximumFractionDigits: 2,
                    })}
                  </td>
                  <td className="py-2.5 text-right text-slate-700">
                    {formatCNY(parseFloat(tx.amount))}
                  </td>
                  <td className="py-2.5 text-right text-slate-500">
                    {parseFloat(tx.fee) > 0
                      ? formatCNY(parseFloat(tx.fee))
                      : '—'}
                  </td>
                  <td className="py-2.5 pl-4 text-slate-400">
                    {tx.note || '—'}
                  </td>
                  <td className="py-2.5 text-center">
                    <button
                      onClick={() => handleDeleteTx(tx.id)}
                      disabled={deletingTx === tx.id}
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
        </div>
      )}
    </div>
  )
}
