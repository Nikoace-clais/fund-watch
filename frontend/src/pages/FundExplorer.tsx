import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router'
import { Search, Filter, ArrowUpDown } from 'lucide-react'
import { fetchFundsOverview, fetchFundDetail } from '@/lib/api'
import { cn, formatPercent } from '@/lib/utils'
import { useColor } from '@/lib/color-context'

type OverviewItem = {
  fund: { code: string; name?: string; sector?: string; holding_shares?: string; created_at: string }
  latest?: { code: string; name?: string; gsz?: number; gszzl?: number; gztime?: string; dwjz?: number } | null
  has_transactions: boolean
}

type DetailData = {
  fund_type?: string
  three_month_return?: number
  one_year_return?: number
}

type SortKey = 'code' | 'name' | 'gsz' | 'gszzl' | 'three_month' | 'one_year'
type SortDir = 'asc' | 'desc'

export function FundExplorer() {
  const { colorFor } = useColor()
  const [items, setItems] = useState<OverviewItem[]>([])
  const [details, setDetails] = useState<Record<string, DetailData>>({})
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('code')
  const [sortDir, setSortDir] = useState<SortDir>('asc')

  // Load overview list
  useEffect(() => {
    setLoading(true)
    fetchFundsOverview()
      .then((data) => setItems(data.items ?? []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  // Async load details for each fund
  useEffect(() => {
    if (items.length === 0) return
    for (const item of items) {
      const code = item.fund.code
      if (details[code]) continue
      fetchFundDetail(code)
        .then((d) => {
          setDetails((prev) => ({
            ...prev,
            [code]: {
              fund_type: d.fund_type,
              three_month_return: d.three_month_return,
              one_year_return: d.one_year_return,
            },
          }))
        })
        .catch(() => {})
    }
  }, [items]) // eslint-disable-line react-hooks/exhaustive-deps

  // Derive unique fund types for the filter dropdown
  const fundTypes = useMemo(() => {
    const types = new Set<string>()
    for (const code of Object.keys(details)) {
      const t = details[code]?.fund_type
      if (t) types.add(t)
    }
    return Array.from(types).sort()
  }, [details])

  // Toggle sort
  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  // Filtered + sorted items
  const filtered = useMemo(() => {
    let list = items

    // Search filter
    if (search.trim()) {
      const q = search.trim().toLowerCase()
      list = list.filter(
        (item) =>
          item.fund.code.includes(q) ||
          (item.latest?.name ?? item.fund.name ?? '').toLowerCase().includes(q),
      )
    }

    // Type filter
    if (typeFilter) {
      list = list.filter((item) => details[item.fund.code]?.fund_type === typeFilter)
    }

    // Sort
    const sorted = [...list]
    sorted.sort((a, b) => {
      let va: number | string = 0
      let vb: number | string = 0
      const da = details[a.fund.code]
      const db = details[b.fund.code]

      switch (sortKey) {
        case 'code':
          va = a.fund.code
          vb = b.fund.code
          break
        case 'name':
          va = (a.latest?.name ?? a.fund.name ?? '').toLowerCase()
          vb = (b.latest?.name ?? b.fund.name ?? '').toLowerCase()
          break
        case 'gsz':
          va = a.latest?.gsz ?? -Infinity
          vb = b.latest?.gsz ?? -Infinity
          break
        case 'gszzl':
          va = a.latest?.gszzl ?? -Infinity
          vb = b.latest?.gszzl ?? -Infinity
          break
        case 'three_month':
          va = da?.three_month_return ?? -Infinity
          vb = db?.three_month_return ?? -Infinity
          break
        case 'one_year':
          va = da?.one_year_return ?? -Infinity
          vb = db?.one_year_return ?? -Infinity
          break
      }

      if (va < vb) return sortDir === 'asc' ? -1 : 1
      if (va > vb) return sortDir === 'asc' ? 1 : -1
      return 0
    })

    return sorted
  }, [items, search, typeFilter, sortKey, sortDir, details])

  const SortHeader = ({ label, field }: { label: string; field: SortKey }) => (
    <th
      className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 cursor-pointer select-none hover:text-slate-700"
      onClick={() => toggleSort(field)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        <ArrowUpDown className={cn('h-3.5 w-3.5', sortKey === field ? 'text-blue-600' : 'text-slate-400')} />
      </span>
    </th>
  )

  return (
    <div>
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">基金市场</h1>
          <p className="text-sm text-slate-500 mt-1">发现并筛选优质公募基金产品。</p>
        </div>

        <div className="flex flex-col sm:flex-row gap-3">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="搜索代码或名称..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full sm:w-64 pl-10 pr-4 py-2 text-sm rounded-lg border-0 ring-1 ring-slate-300 focus:ring-2 focus:ring-blue-600 outline-none bg-white"
            />
          </div>

          {/* Type filter */}
          <div className="relative">
            <Filter className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="w-full sm:w-44 pl-10 pr-4 py-2 text-sm rounded-lg border-0 ring-1 ring-slate-300 focus:ring-2 focus:ring-blue-600 outline-none bg-white appearance-none cursor-pointer"
            >
              <option value="">全部类型</option>
              {fundTypes.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-20 text-slate-400 text-sm">
            加载中...
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-slate-400">
            <Search className="h-10 w-10 mb-3 text-slate-300" />
            <p className="text-sm">没有找到匹配的基金</p>
            {(search || typeFilter) && (
              <button
                className="mt-2 text-xs text-blue-600 hover:underline"
                onClick={() => {
                  setSearch('')
                  setTypeFilter('')
                }}
              >
                清除筛选条件
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <SortHeader label="基金代码" field="code" />
                  <SortHeader label="基金简称" field="name" />
                  <SortHeader label="单位净值" field="gsz" />
                  <SortHeader label="日涨跌幅" field="gszzl" />
                  <SortHeader label="近3月收益" field="three_month" />
                  <SortHeader label="近1年收益" field="one_year" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filtered.map((item) => {
                  const code = item.fund.code
                  const name = item.latest?.name ?? item.fund.name ?? '-'
                  const detail = details[code]
                  const fundType = detail?.fund_type
                  const gsz = item.latest?.gsz
                  const gszzl = item.latest?.gszzl
                  const threeMonth = detail?.three_month_return
                  const oneYear = detail?.one_year_return

                  return (
                    <tr key={code} className="hover:bg-blue-50/50 transition-colors">
                      <td className="px-4 py-3">
                        <Link
                          to={`/funds/${code}`}
                          className="text-sm font-mono text-blue-600 hover:underline"
                        >
                          {code}
                        </Link>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <Link
                            to={`/funds/${code}`}
                            className="text-sm font-medium text-slate-800 hover:text-blue-600 hover:underline"
                          >
                            {name}
                          </Link>
                          {fundType && (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700">
                              {fundType}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-700 tabular-nums">
                        {gsz != null ? gsz.toFixed(4) : '\u2014'}
                      </td>
                      <td className={cn('px-4 py-3 text-sm font-medium tabular-nums', gszzl != null ? colorFor(gszzl) : 'text-slate-400')}>
                        {gszzl != null ? formatPercent(gszzl) : '\u2014'}
                      </td>
                      <td className={cn('px-4 py-3 text-sm font-medium tabular-nums', threeMonth != null ? colorFor(threeMonth) : 'text-slate-400')}>
                        {threeMonth != null ? formatPercent(threeMonth) : '\u2014'}
                      </td>
                      <td className={cn('px-4 py-3 text-sm font-medium tabular-nums', oneYear != null ? colorFor(oneYear) : 'text-slate-400')}>
                        {oneYear != null ? formatPercent(oneYear) : '\u2014'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
