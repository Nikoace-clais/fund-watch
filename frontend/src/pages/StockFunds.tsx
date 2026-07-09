import { useState } from 'react'
import { Link } from 'react-router'
import { Search, Building2 } from 'lucide-react'
import type { FundHolderItem } from '@/lib/api'
import { useStockFundsHolding } from '@/lib/queries'
import { formatCNY } from '@/lib/utils'
import { ErrorBanner, PageState } from '@/components/PageState'

/* ── 万元 → 亿 display ─────────────────────────────────────────────────────── */
function fmtMarketCap(v: number | null) {
  if (v == null) return '—'
  // HOLD_MARKET_CAP is in yuan
  const yi = v / 1e8
  return yi >= 1 ? `${yi.toFixed(2)} 亿` : formatCNY(v)
}

/* ── table row ──────────────────────────────────────────────────────────────── */
function FundRow({ item, rank }: { item: FundHolderItem; rank: number }) {
  return (
    <tr className="border-t border-slate-100 hover:bg-slate-50 transition-colors">
      <td className="px-4 py-3 text-sm text-slate-400 tabular-nums w-10">
        {rank}
      </td>
      <td className="px-4 py-3">
        <Link
          to={`/funds/${item.code}`}
          className="font-mono text-sm text-blue-600 hover:underline"
        >
          {item.code}
        </Link>
      </td>
      <td className="px-4 py-3 text-sm text-slate-800">{item.name}</td>
      <td className="px-4 py-3 text-sm text-slate-500">
        {item.company ? (
          <span className="inline-flex items-center gap-1">
            <Building2 className="h-3 w-3 shrink-0 text-slate-400" />
            {item.company}
          </span>
        ) : (
          '—'
        )}
      </td>
      <td className="px-4 py-3 text-sm text-slate-800 tabular-nums text-right">
        {fmtMarketCap(item.hold_market_cap)}
      </td>
      <td className="px-4 py-3 text-sm tabular-nums text-right">
        {item.netasset_ratio != null ? (
          <span className="text-slate-800">
            {item.netasset_ratio.toFixed(2)}%
          </span>
        ) : (
          <span className="text-slate-400">—</span>
        )}
      </td>
    </tr>
  )
}

/* ── main page ──────────────────────────────────────────────────────────────── */
export function StockFunds() {
  const [input, setInput] = useState('')
  const [code, setCode] = useState('')

  function handleSearch() {
    const trimmed = input.trim()
    if (/^\d{6}$/.test(trimmed)) setCode(trimmed)
  }

  const { data, isLoading, error } = useStockFundsHolding(code)

  const errMsg =
    error instanceof Error ? error.message : error ? '数据加载失败' : null

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <Search className="h-6 w-6 text-blue-600" />
          持仓反查
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          输入 A 股 6 位股票代码，查询持有该股票的公募基金（季报持仓）
        </p>
      </div>

      {/* Search box */}
      <div className="flex gap-2 max-w-sm">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          placeholder="股票代码，如 600519"
          maxLength={6}
          className="flex-1 px-3 py-2 text-sm rounded-lg border border-slate-200 bg-white
                     focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder-slate-400"
        />
        <button
          onClick={handleSearch}
          disabled={!/^\d{6}$/.test(input.trim())}
          className="px-4 py-2 text-sm rounded-lg bg-blue-600 text-white font-medium
                     hover:bg-blue-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          查询
        </button>
      </div>

      {/* Error */}
      {errMsg && <ErrorBanner>{errMsg}</ErrorBanner>}

      {/* Loading */}
      {isLoading && <PageState loading />}

      {/* Results */}
      {data && !isLoading && (
        <div className="space-y-3">
          {/* Meta */}
          <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 text-sm text-slate-500">
            <span className="font-medium text-slate-800 text-base">
              {data.stock_name ?? code}
            </span>
            <span>
              共{' '}
              <span className="font-semibold text-slate-900">
                {data.count.toLocaleString()}
              </span>{' '}
              只基金持有
            </span>
            {data.report_date && (
              <span
                className="text-xs bg-amber-50 text-amber-700 border border-amber-200
                               px-2 py-0.5 rounded-full"
              >
                数据口径：{data.report_date} 季报
              </span>
            )}
          </div>

          {data.items.length === 0 ? (
            <PageState empty emptyContent="暂无持仓数据" />
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
              <table className="w-full text-left">
                <thead>
                  <tr className="bg-slate-50 text-xs text-slate-500 uppercase tracking-wide">
                    <th className="px-4 py-3 w-10">#</th>
                    <th className="px-4 py-3">代码</th>
                    <th className="px-4 py-3">基金名称</th>
                    <th className="px-4 py-3">基金公司</th>
                    <th className="px-4 py-3 text-right">持仓市值</th>
                    <th className="px-4 py-3 text-right">占净值</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((item, i) => (
                    <FundRow key={item.code} item={item} rank={i + 1} />
                  ))}
                </tbody>
              </table>
              {data.count > data.items.length && (
                <p className="px-4 py-3 text-xs text-slate-400 border-t border-slate-100 text-center">
                  显示前 {data.items.length} 条，共{' '}
                  {data.count.toLocaleString()} 条
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Idle hint */}
      {!code && !isLoading && (
        <p className="text-sm text-slate-400">
          示例：600519（贵州茅台）、000858（五粮液）、601318（中国平安）
        </p>
      )}
    </div>
  )
}
