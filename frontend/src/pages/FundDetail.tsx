import { useEffect, useState, useMemo } from 'react'
import { useParams, Link } from 'react-router'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ReferenceDot,
  PieChart as RechartsPieChart, Pie, Cell, Legend,
} from 'recharts'
import { ArrowLeft, Plus, Share2, Info, TrendingUp, PieChart, Activity } from 'lucide-react'
import { fetchFundDetail, fetchNavHistory, fetchFundHoldings, fetchQuote, addFund, fetchTransactions, type Transaction } from '@/lib/api'
import { cn, formatPercent } from '@/lib/utils'
import { useColor } from '@/lib/color-context'

/* ---------- types ---------- */
type FundDetailData = {
  code: string
  name?: string
  fund_type?: string
  manager?: string
  size?: number
  established_date?: string
  one_month_return?: number
  three_month_return?: number
  six_month_return?: number
  one_year_return?: number
  asset_allocation: Array<{ name: string; value: number }>
  sector?: string
}

type NavPoint = { date: string; nav: number; accNav?: number; dailyReturn?: number }

type Holding = { stock_code: string; stock_name: string; percentage: number | null }

type Quote = { fundcode: string; name?: string; dwjz?: number; gsz?: number; gszzl?: number; gztime?: string }

/* ---------- constants ---------- */
const PIE_COLORS = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6']

const RANGE_OPTIONS = [
  { label: '1月', days: 21 },
  { label: '3月', days: 63 },
  { label: '半年', days: 126 },
  { label: '1年', days: 252 },
  { label: '全部', days: 0 },
] as const

/* ---------- helpers ---------- */
function simplifyAssetName(name: string) {
  if (name.includes('股票')) return '股票'
  if (name.includes('债券')) return '债券'
  if (name.includes('现金')) return '现金'
  if (name.includes('基金')) return '基金'
  // strip "占净比" etc.
  return name.replace(/占净比/g, '').trim()
}

function formatDate(dateStr: string) {
  const d = new Date(dateStr)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

/* ---------- component ---------- */
export function FundDetail() {
  const { code } = useParams<{ code: string }>()

  const [detail, setDetail] = useState<FundDetailData | null>(null)
  const [history, setHistory] = useState<NavPoint[]>([])
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [quote, setQuote] = useState<Quote | null>(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [range, setRange] = useState<number>(63) // default 3M
  const [addMsg, setAddMsg] = useState('')
  const [transactions, setTransactions] = useState<Transaction[]>([])

  useEffect(() => {
    if (!code) return
    setLoading(true)
    setNotFound(false)

    Promise.allSettled([
      fetchFundDetail(code),
      fetchNavHistory(code, 500),
      fetchFundHoldings(code),
      fetchQuote(code),
      fetchTransactions(code),
    ]).then(([detailRes, navRes, holdRes, quoteRes, txRes]) => {
      if (detailRes.status === 'fulfilled') {
        setDetail(detailRes.value)
      } else {
        setNotFound(true)
      }
      if (navRes.status === 'fulfilled') setHistory(navRes.value.history)
      if (holdRes.status === 'fulfilled') setHoldings(holdRes.value.holdings)
      if (quoteRes.status === 'fulfilled') setQuote(quoteRes.value)
      if (txRes.status === 'fulfilled') setTransactions(txRes.value.items)
      setLoading(false)
    })
  }, [code])

  const filteredHistory = useMemo(() => {
    if (range === 0) return history
    return history.slice(-range)
  }, [history, range])

  const tradeMap = useMemo(() => {
    const map = new Map<string, Transaction[]>()
    for (const tx of transactions) {
      const list = map.get(tx.trade_date) ?? []
      list.push(tx)
      map.set(tx.trade_date, list)
    }
    return map
  }, [transactions])

  const assetData = useMemo(() => {
    if (!detail) return []
    return detail.asset_allocation
      .filter((a) => a.value > 0)
      .map((a) => ({ name: simplifyAssetName(a.name), value: a.value }))
  }, [detail])

  const { colorFor } = useColor()
  const navValue = quote?.gsz ?? (history.length > 0 ? history[history.length - 1].nav : null)
  const changeValue = quote?.gszzl ?? null

  async function handleAddFund() {
    if (!code) return
    try {
      await addFund(code)
      setAddMsg('已加入自选')
      setTimeout(() => setAddMsg(''), 3000)
    } catch {
      setAddMsg('加入失败')
      setTimeout(() => setAddMsg(''), 3000)
    }
  }

  /* ---- loading / not found ---- */
  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <p className="text-slate-400 text-lg">加载中...</p>
      </div>
    )
  }

  if (notFound || !detail) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] text-center">
        <p className="text-xl text-slate-500 mb-4">未找到该基金</p>
        <Link to="/market" className="text-blue-600 hover:underline flex items-center gap-1">
          <ArrowLeft className="h-4 w-4" /> 返回基金列表
        </Link>
      </div>
    )
  }

  const stageReturns = [
    { label: '近1月', value: detail.one_month_return },
    { label: '近3月', value: detail.three_month_return },
    { label: '近6月', value: detail.six_month_return },
    { label: '近1年', value: detail.one_year_return },
  ]

  return (
    <div className="space-y-6">
      {/* ---- Top bar ---- */}
      <div className="flex items-center justify-between">
        <Link
          to="/market"
          className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-blue-600 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" /> 返回
        </Link>
        <div className="flex items-center gap-2">
          <button
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 transition-colors"
          >
            <Share2 className="h-4 w-4" /> 分享
          </button>
          <button
            onClick={handleAddFund}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors"
          >
            <Plus className="h-4 w-4" /> 加入自选
          </button>
          {addMsg && (
            <span className="text-sm text-green-600 font-medium">{addMsg}</span>
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
            <p className="text-xs text-slate-400 mb-1">单位净值(估)</p>
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
          {/* NAV trend chart */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-slate-600" />
                <h2 className="text-lg font-semibold text-slate-800">净值走势</h2>
              </div>
              {/* range selector */}
              <div className="flex bg-slate-100 rounded-lg p-1">
                {RANGE_OPTIONS.map((opt) => (
                  <button
                    key={opt.label}
                    onClick={() => setRange(opt.days)}
                    className={cn(
                      'px-3 py-1 text-xs font-medium rounded-md transition-all',
                      range === opt.days
                        ? 'bg-white text-slate-900 shadow-sm'
                        : 'text-slate-500 hover:text-slate-700',
                    )}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {filteredHistory.length === 0 ? (
              <div className="flex items-center justify-center h-[300px] text-slate-400">
                暂无净值数据
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={filteredHistory} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
                  <defs>
                    <linearGradient id="navGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={formatDate}
                    tick={{ fontSize: 11, fill: '#94a3b8' }}
                    axisLine={{ stroke: '#e2e8f0' }}
                    tickLine={false}
                  />
                  <YAxis
                    orientation="right"
                    tickFormatter={(v: number) => v.toFixed(4)}
                    tick={{ fontSize: 11, fill: '#94a3b8' }}
                    axisLine={false}
                    tickLine={false}
                    domain={['auto', 'auto']}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      border: 'none',
                      borderRadius: '8px',
                      color: '#fff',
                      fontSize: 13,
                    }}
                    labelStyle={{ color: '#94a3b8' }}
                    formatter={(value: number) => [value.toFixed(4), '净值']}
                    labelFormatter={(label: string) => `日期: ${label}`}
                  />
                  <Area
                    type="monotone"
                    dataKey="nav"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    fill="url(#navGradient)"
                    dot={false}
                    activeDot={{ r: 4, strokeWidth: 2, fill: '#fff', stroke: '#3b82f6' }}
                  />
                  {filteredHistory.flatMap((point) => {
                    const txs = tradeMap.get(point.date)
                    if (!txs || txs.length === 0) return []
                    // 同日有买入优先显示买入色
                    const hasBuy = txs.some((t) => t.direction === 'buy')
                    const color = hasBuy ? '#ef4444' : '#10b981'
                    return [
                      <ReferenceDot
                        key={point.date}
                        x={point.date}
                        y={point.nav}
                        r={5}
                        fill={color}
                        stroke="#fff"
                        strokeWidth={2}
                      />
                    ]
                  })}
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* Stage returns table */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <div className="flex items-center gap-2 mb-4">
              <Activity className="h-5 w-5 text-slate-600" />
              <h2 className="text-lg font-semibold text-slate-800">阶段涨幅</h2>
            </div>
            <div className="grid grid-cols-4 gap-4">
              {stageReturns.map((item) => (
                <div key={item.label} className="text-center p-3 bg-slate-50 rounded-lg">
                  <p className="text-xs text-slate-400 mb-1">{item.label}</p>
                  {item.value != null ? (
                    <p className={cn('text-lg font-bold', colorFor(item.value))}>
                      {formatPercent(item.value)}
                    </p>
                  ) : (
                    <p className="text-lg font-bold text-slate-300">--</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right column */}
        <div className="space-y-6">
          {/* Asset allocation pie chart */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <div className="flex items-center gap-2 mb-4">
              <PieChart className="h-5 w-5 text-slate-600" />
              <h2 className="text-lg font-semibold text-slate-800">资产配置</h2>
            </div>
            {assetData.length === 0 ? (
              <div className="flex items-center justify-center h-[200px] text-slate-400 text-sm">
                暂无配置数据
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={240}>
                <RechartsPieChart>
                  <Pie
                    data={assetData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={80}
                    paddingAngle={2}
                    label={({ name, value }) => `${name} ${value.toFixed(1)}%`}
                  >
                    {assetData.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value: number) => `${value.toFixed(2)}%`} />
                  <Legend />
                </RechartsPieChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* Top holdings */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <div className="flex items-center gap-2 mb-4">
              <Info className="h-5 w-5 text-slate-600" />
              <h2 className="text-lg font-semibold text-slate-800">重仓股票</h2>
            </div>
            {holdings.length === 0 ? (
              <div className="flex items-center justify-center h-[120px] text-slate-400 text-sm">
                暂无持仓数据
              </div>
            ) : (
              <div className="space-y-3">
                {holdings.map((h) => (
                  <div key={h.stock_code}>
                    <div className="flex items-center justify-between text-sm mb-1">
                      <span className="text-slate-700 font-medium truncate mr-2">
                        {h.stock_name}
                      </span>
                      <span className="text-slate-500 text-xs whitespace-nowrap">
                        {h.percentage != null ? `${h.percentage.toFixed(2)}%` : '--'}
                      </span>
                    </div>
                    <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-blue-500 rounded-full transition-all"
                        style={{
                          width: `${Math.min((h.percentage ?? 0) / 15 * 100, 100)}%`,
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
