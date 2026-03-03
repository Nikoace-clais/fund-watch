import Decimal from 'decimal.js'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
  PieChart, Pie, Cell,
} from 'recharts'

type FundOverview = {
  fund: {
    code: string
    name?: string | null
    sector?: string | null
    amount?: number | null
    percentage?: number | null
    amount_mode?: string | null
    holding_shares?: string | null
    created_at: string
  }
  latest?: {
    code: string
    name?: string | null
    gsz?: number | null
    gszzl?: number | null
    gztime?: string | null
    captured_at?: string | null
  } | null
}

type OcrMatchedFund = {
  code: string
  amount?: number | null
}

type OcrResp = {
  matched_codes: string[]
  matched_funds: OcrMatchedFund[]
  raw_text: string
}

type Snapshot = {
  captured_at: string
  gsz?: number | null
  gszzl?: number | null
  gztime?: string | null
}

type Holding = {
  stock_code: string
  stock_name: string
  percentage: number | null
  shares_wan: number | null
  value_wan: number | null
}

type Transaction = {
  id: number
  code: string
  direction: 'buy' | 'sell'
  trade_date: string
  nav: string
  shares: string
  amount: string
  fee: string
  note?: string | null
  source: string
  created_at: string
}

type PnlData = {
  has_transactions: boolean
  holding_shares?: string
  total_cost?: string
  avg_cost_nav?: string
  pnl?: string | null
  pnl_rate?: string | null
  current_nav?: string | null
}

const API = 'http://127.0.0.1:8010'
const PIE_COLORS = ['#2563eb', '#15803d', '#dc2626', '#d97706', '#7c3aed', '#0891b2', '#be185d', '#4f46e5']

export function App() {
  const [funds, setFunds] = useState<FundOverview[]>([])
  const [ocrCodes, setOcrCodes] = useState<string[]>([])
  const [ocrFunds, setOcrFunds] = useState<OcrMatchedFund[]>([])
  const [loading, setLoading] = useState(false)
  const [msg, setMsg] = useState('')
  const [manualCode, setManualCode] = useState('')
  const [manualAmount, setManualAmount] = useState('')
  const [selectedCode, setSelectedCode] = useState<string | null>(null)
  const [snapshots, setSnapshots] = useState<Snapshot[]>([])
  const [editingAmount, setEditingAmount] = useState<string | null>(null)
  const [editAmountVal, setEditAmountVal] = useState('')
  const [holdingsCode, setHoldingsCode] = useState<string | null>(null)
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [refreshing, setRefreshing] = useState(false)
  const [lastRefresh, setLastRefresh] = useState<string | null>(null)

  // Transaction state
  const [txCode, setTxCode] = useState<string | null>(null)
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [pnl, setPnl] = useState<PnlData | null>(null)
  const [txForm, setTxForm] = useState({
    direction: 'buy' as 'buy' | 'sell',
    trade_date: new Date().toISOString().slice(0, 10),
    nav: '',
    shares: '',
    fee: '0',
    note: '',
  })

  const dedupedCodes = useMemo(() => Array.from(new Set(ocrCodes)), [ocrCodes])

  const pieData = useMemo(() => {
    return funds
      .filter((f) => f.fund.amount != null && f.fund.amount > 0)
      .map((f) => ({
        name: f.fund.sector
          ? `${f.latest?.name || f.fund.name || f.fund.code}(${f.fund.sector})`
          : (f.latest?.name || f.fund.name || f.fund.code),
        value: f.fund.amount!,
      }))
  }, [funds])

  async function loadFunds() {
    const res = await fetch(`${API}/api/funds/overview`)
    const data = await res.json()
    setFunds(data.items ?? [])
  }

  useEffect(() => {
    loadFunds().catch(() => setMsg('加载基金池失败'))
  }, [])

  async function loadSnapshots(code: string) {
    if (selectedCode === code) {
      setSelectedCode(null)
      setSnapshots([])
      return
    }
    setSelectedCode(code)
    const res = await fetch(`${API}/api/snapshots/${code}?limit=200`)
    const data = await res.json()
    const items: Snapshot[] = data.items ?? []
    setSnapshots(items)
  }

  const refreshData = useCallback(async () => {
    setRefreshing(true)
    try {
      await fetch(`${API}/api/snapshots/pull`, { method: 'POST' })
      await loadFunds()
      if (selectedCode) {
        const res = await fetch(`${API}/api/snapshots/${selectedCode}?limit=200`)
        const data = await res.json()
        const items: Snapshot[] = data.items ?? []
        setSnapshots(items)
      }
      setLastRefresh(new Date().toLocaleTimeString())
    } catch {
      setMsg('刷新失败')
    } finally {
      setRefreshing(false)
    }
  }, [selectedCode])

  // Auto-refresh every 3 minutes during trading hours, 15 minutes otherwise
  useEffect(() => {
    function getInterval() {
      const now = new Date()
      const h = now.getHours(), m = now.getMinutes()
      const t = h * 60 + m
      const isTradingDay = now.getDay() >= 1 && now.getDay() <= 5
      const isTradingHour = (t >= 570 && t <= 690) || (t >= 780 && t <= 900) // 9:30-11:30, 13:00-15:00
      return isTradingDay && isTradingHour ? 3 * 60 * 1000 : 15 * 60 * 1000
    }
    const timer = setInterval(refreshData, getInterval())
    return () => clearInterval(timer)
  }, [refreshData])

  async function onUpload(file: File) {
    setLoading(true)
    setMsg('')
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(`${API}/api/ocr/fund-code`, { method: 'POST', body: form })
      if (!res.ok) throw new Error('OCR 请求失败')
      const data: OcrResp = await res.json()
      const funds = (data.matched_funds || []).filter((f) => /^\d{6}$/.test(f.code))
      const codes = funds.map((f) => f.code)
      setOcrCodes(codes)
      setOcrFunds(funds)
      const summary = funds.map((f) => f.amount ? `${f.code}(¥${f.amount})` : f.code).join(', ')
      setMsg(`识别完成：${summary || '未识别到基金代码'}`)
    } catch (e) {
      setMsg(e instanceof Error ? e.message : '上传失败')
    } finally {
      setLoading(false)
    }
  }

  async function addFund(code: string, amount?: number | null) {
    setMsg('')
    const opts: RequestInit = { method: 'POST' }
    if (amount != null) {
      opts.headers = { 'Content-Type': 'application/json' }
      opts.body = JSON.stringify({ amount })
    }
    const res = await fetch(`${API}/api/funds/${code}`, opts)
    if (!res.ok) {
      setMsg(`添加 ${code} 失败`)
      return
    }
    await fetch(`${API}/api/funds/recalc-percentage`, { method: 'POST' })
    await loadFunds()
    setMsg(`已加入基金池：${code}`)
  }

  async function addFundManual() {
    const code = manualCode.trim()
    if (!/^\d{6}$/.test(code)) {
      setMsg('请输入 6 位基金代码')
      return
    }
    const amt = manualAmount.trim() ? parseFloat(manualAmount) : undefined
    await addFund(code, amt)
    setManualCode('')
    setManualAmount('')
  }

  async function addAllOcrCodes() {
    if (dedupedCodes.length === 0) return
    const amounts: Record<string, number> = {}
    for (const f of ocrFunds) {
      if (f.amount != null) amounts[f.code] = f.amount
    }
    const res = await fetch(`${API}/api/funds/batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codes: dedupedCodes, amounts: Object.keys(amounts).length > 0 ? amounts : undefined }),
    })
    if (!res.ok) {
      setMsg('批量加入失败')
      return
    }
    const data = await res.json()
    await fetch(`${API}/api/funds/recalc-percentage`, { method: 'POST' })
    await loadFunds()
    setMsg(`批量加入完成：${(data.added || []).join(', ') || '无新增'}${(data.invalid || []).length ? `；无效：${data.invalid.join(',')}` : ''}`)
  }

  async function loadHoldings(code: string) {
    if (holdingsCode === code) {
      setHoldingsCode(null)
      setHoldings([])
      return
    }
    setHoldingsCode(code)
    try {
      const res = await fetch(`${API}/api/funds/${code}/holdings`)
      const data = await res.json()
      setHoldings(data.holdings ?? [])
    } catch {
      setHoldings([])
    }
  }

  async function saveAmount(code: string, amount: number) {
    await fetch(`${API}/api/funds/${code}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ amount }),
    })
    await fetch(`${API}/api/funds/recalc-percentage`, { method: 'POST' })
    await loadFunds()
    setEditingAmount(null)
  }

  // ── Transaction functions ──

  async function loadTransactions(code: string) {
    if (txCode === code) {
      setTxCode(null)
      setTransactions([])
      setPnl(null)
      return
    }
    setTxCode(code)
    const [txRes, pnlRes] = await Promise.all([
      fetch(`${API}/api/funds/${code}/transactions`),
      fetch(`${API}/api/funds/${code}/pnl`),
    ])
    const txData = await txRes.json()
    const pnlData = await pnlRes.json()
    setTransactions(txData.items ?? [])
    setPnl(pnlData)
  }

  async function addTransaction() {
    if (!txCode) return
    if (!txForm.nav || !txForm.shares) {
      setMsg('请填写净值和份额')
      return
    }
    const res = await fetch(`${API}/api/funds/${txCode}/transactions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(txForm),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      setMsg(err.detail || '添加交易失败')
      return
    }
    setTxForm({ ...txForm, nav: '', shares: '', fee: '0', note: '' })
    // Reload transactions and pnl
    const [txRes, pnlRes] = await Promise.all([
      fetch(`${API}/api/funds/${txCode}/transactions`),
      fetch(`${API}/api/funds/${txCode}/pnl`),
    ])
    setTransactions((await txRes.json()).items ?? [])
    setPnl(await pnlRes.json())
    await fetch(`${API}/api/funds/recalc-percentage`, { method: 'POST' })
    await loadFunds()
    setMsg('交易记录已添加')
  }

  async function deleteTransaction(id: number) {
    if (!confirm('确定删除此交易记录？')) return
    await fetch(`${API}/api/transactions/${id}`, { method: 'DELETE' })
    if (txCode) {
      const [txRes, pnlRes] = await Promise.all([
        fetch(`${API}/api/funds/${txCode}/transactions`),
        fetch(`${API}/api/funds/${txCode}/pnl`),
      ])
      setTransactions((await txRes.json()).items ?? [])
      setPnl(await pnlRes.json())
    }
    await fetch(`${API}/api/funds/recalc-percentage`, { method: 'POST' })
    await loadFunds()
  }

  async function importCsv(file: File) {
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`${API}/api/transactions/csv`, { method: 'POST', body: form })
    const data = await res.json()
    if (data.errors?.length) {
      setMsg(`CSV 导入：${data.imported} 条成功，${data.errors.length} 条失败`)
    } else {
      setMsg(`CSV 导入成功：${data.imported} 条`)
    }
    await fetch(`${API}/api/funds/recalc-percentage`, { method: 'POST' })
    await loadFunds()
    // Reload current tx panel if open
    if (txCode) {
      const [txRes, pnlRes] = await Promise.all([
        fetch(`${API}/api/funds/${txCode}/transactions`),
        fetch(`${API}/api/funds/${txCode}/pnl`),
      ])
      setTransactions((await txRes.json()).items ?? [])
      setPnl(await pnlRes.json())
    }
  }

  async function ocrTransaction(file: File) {
    setLoading(true)
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(`${API}/api/ocr/transaction`, { method: 'POST', body: form })
      const data = await res.json()
      const tx = data.transaction || {}
      setTxForm((prev) => ({
        direction: tx.direction || prev.direction,
        trade_date: tx.trade_date || prev.trade_date,
        nav: tx.nav || prev.nav,
        shares: tx.shares || prev.shares,
        fee: prev.fee,
        note: prev.note,
      }))
      setMsg('OCR 识别完成，请确认预填数据后提交')
    } catch {
      setMsg('OCR 识别失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <h1>Fund Watch</h1>
      <p>上传截图 → OCR识别基金编号 → 一键加入基金池 → 查看估算净值/趋势</p>

      <section className="card">
        <h2>手动添加基金</h2>
        <div className="row">
          <input value={manualCode} placeholder="6 位代码" onChange={(e) => setManualCode(e.target.value)} style={{ flex: 2 }} />
          <input value={manualAmount} placeholder="持仓金额(可选)" onChange={(e) => setManualAmount(e.target.value)} style={{ flex: 1 }} />
          <button onClick={addFundManual}>添加</button>
        </div>
      </section>

      <section className="card">
        <h2>OCR 上传</h2>
        <input
          type="file"
          accept="image/*"
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) onUpload(f)
          }}
        />
        {loading && <p>识别中...</p>}
        {ocrFunds.length > 0 && (
          <>
            <div className="chips">
              {ocrFunds.map((f) => (
                <button key={f.code} onClick={() => addFund(f.code, f.amount)}>
                  加入 {f.code}{f.amount != null ? ` (¥${f.amount})` : ''}
                </button>
              ))}
            </div>
            <button className="batch" onClick={addAllOcrCodes}>
              批量加入全部识别结果
            </button>
          </>
        )}
      </section>

      <section className="card">
        <div className="section-header">
          <h2>基金池（含最新估算）</h2>
          <div className="csv-upload">
            <label>CSV 导入交易：</label>
            <input type="file" accept=".csv" onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) importCsv(f)
            }} />
          </div>
        </div>
        {funds.length === 0 ? (
          <p>暂无基金</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>代码</th>
                <th>名称</th>
                <th>板块</th>
                <th>份额</th>
                <th>持仓金额</th>
                <th>占比%</th>
                <th>估算净值</th>
                <th>估算涨跌%</th>
                <th>涨跌额</th>
                <th>时间</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {funds.map((f) => {
                const isComputed = f.fund.amount_mode === 'computed'
                const shares = f.fund.holding_shares ? new Decimal(f.fund.holding_shares) : null
                const gsz = f.latest?.gsz != null ? new Decimal(f.latest.gsz) : null
                // 持仓金额: computed模式 = 份额×估算净值, manual模式 = 手动输入
                const marketValue = isComputed && shares && gsz
                  ? shares.mul(gsz).toNumber()
                  : f.fund.amount
                return (
                  <tr key={f.fund.code}>
                    <td>{f.fund.code}</td>
                    <td>{f.latest?.name || f.fund.name || '-'}</td>
                    <td>{f.fund.sector || '-'}</td>
                    <td>{shares ? fmtDecimal(f.fund.holding_shares, 2) : '-'}</td>
                    <td
                      className={isComputed ? undefined : 'editable'}
                      onClick={() => {
                        if (!isComputed) {
                          setEditingAmount(f.fund.code)
                          setEditAmountVal(f.fund.amount?.toString() ?? '')
                        }
                      }}
                    >
                      {editingAmount === f.fund.code ? (
                        <input
                          className="inline-input"
                          value={editAmountVal}
                          autoFocus
                          onChange={(e) => setEditAmountVal(e.target.value)}
                          onBlur={() => {
                            const v = parseFloat(editAmountVal)
                            if (!isNaN(v)) saveAmount(f.fund.code, v)
                            else setEditingAmount(null)
                          }}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              const v = parseFloat(editAmountVal)
                              if (!isNaN(v)) saveAmount(f.fund.code, v)
                            } else if (e.key === 'Escape') {
                              setEditingAmount(null)
                            }
                          }}
                        />
                      ) : (
                        marketValue != null ? fmtAmount(marketValue) : '点击输入'
                      )}
                    </td>
                    <td>{f.fund.percentage != null ? `${f.fund.percentage}%` : '-'}</td>
                    <td>{fmtNum(f.latest?.gsz)}</td>
                    <td className={Number(f.latest?.gszzl || 0) >= 0 ? 'up' : 'down'}>{fmtNum(f.latest?.gszzl)}</td>
                    <td className={Number(f.latest?.gszzl || 0) >= 0 ? 'up' : 'down'}>
                      {marketValue != null && f.latest?.gszzl != null
                        ? fmtAmount(marketValue * f.latest.gszzl / 100)
                        : '-'}
                    </td>
                    <td>{f.latest?.gztime || '-'}</td>
                    <td className="actions">
                      <button onClick={() => loadTransactions(f.fund.code)}>
                        {txCode === f.fund.code ? '收起' : '交易'}
                      </button>
                      <button className="secondary" onClick={() => loadSnapshots(f.fund.code)}>趋势</button>
                      <button className="secondary" onClick={() => loadHoldings(f.fund.code)}>重仓</button>
                    </td>
                  </tr>
                )
              })}
              {(() => {
                // Compute total market value per fund
                const totalMarketValue = funds.reduce((sum, f) => {
                  const isComputed = f.fund.amount_mode === 'computed'
                  const shares = f.fund.holding_shares ? new Decimal(f.fund.holding_shares) : null
                  const gsz = f.latest?.gsz != null ? new Decimal(f.latest.gsz) : null
                  const mv = isComputed && shares && gsz ? shares.mul(gsz).toNumber() : (f.fund.amount ?? 0)
                  return sum + mv
                }, 0)
                const totalPnl = funds.reduce((sum, f) => {
                  const isComputed = f.fund.amount_mode === 'computed'
                  const shares = f.fund.holding_shares ? new Decimal(f.fund.holding_shares) : null
                  const gsz = f.latest?.gsz != null ? new Decimal(f.latest.gsz) : null
                  const mv = isComputed && shares && gsz ? shares.mul(gsz).toNumber() : (f.fund.amount ?? 0)
                  if (mv && f.latest?.gszzl != null)
                    return sum + mv * f.latest.gszzl / 100
                  return sum
                }, 0)
                return (
                  <tr style={{ fontWeight: 'bold' }}>
                    <td>合计</td>
                    <td></td>
                    <td></td>
                    <td></td>
                    <td>{totalMarketValue > 0 ? fmtAmount(totalMarketValue) : '-'}</td>
                    <td></td>
                    <td></td>
                    <td></td>
                    <td className={totalPnl >= 0 ? 'up' : 'down'}>{totalMarketValue > 0 ? fmtAmount(totalPnl) : '-'}</td>
                    <td></td>
                    <td></td>
                  </tr>
                )
              })()}
            </tbody>
          </table>
        )}
      </section>

      {/* Transaction panel */}
      {txCode && (
        <section className="card">
          <h2>交易记录 · {txCode}</h2>

          {/* PnL summary */}
          {pnl?.has_transactions && (
            <div className="pnl-card">
              <div className="pnl-item">
                <div className="label">持有份额</div>
                <div className="value">{fmtDecimal(pnl.holding_shares)}</div>
              </div>
              <div className="pnl-item">
                <div className="label">成本均价</div>
                <div className="value">{fmtDecimal(pnl.avg_cost_nav, 4)}</div>
              </div>
              <div className="pnl-item">
                <div className="label">总成本</div>
                <div className="value">{fmtDecimal(pnl.total_cost)}</div>
              </div>
              <div className="pnl-item">
                <div className="label">当前估算净值</div>
                <div className="value">{pnl.current_nav ?? '-'}</div>
              </div>
              <div className="pnl-item">
                <div className="label">浮动盈亏</div>
                <div className={`value ${pnlClass(pnl.pnl)}`}>
                  {pnl.pnl != null ? `${Number(pnl.pnl) >= 0 ? '+' : ''}${pnl.pnl}` : '-'}
                </div>
              </div>
              <div className="pnl-item">
                <div className="label">盈亏率</div>
                <div className={`value ${pnlClass(pnl.pnl_rate)}`}>
                  {pnl.pnl_rate != null ? `${Number(pnl.pnl_rate) >= 0 ? '+' : ''}${pnl.pnl_rate}%` : '-'}
                </div>
              </div>
            </div>
          )}

          {/* Add transaction form */}
          <div className="tx-form">
            <select value={txForm.direction} onChange={(e) => setTxForm({ ...txForm, direction: e.target.value as 'buy' | 'sell' })}>
              <option value="buy">买入</option>
              <option value="sell">卖出</option>
            </select>
            <input type="date" value={txForm.trade_date} onChange={(e) => setTxForm({ ...txForm, trade_date: e.target.value })} />
            <input type="text" placeholder="净值" value={txForm.nav} onChange={(e) => setTxForm({ ...txForm, nav: e.target.value })} />
            <input type="text" placeholder="份额" value={txForm.shares} onChange={(e) => setTxForm({ ...txForm, shares: e.target.value })} />
            <input type="text" placeholder="手续费" value={txForm.fee} onChange={(e) => setTxForm({ ...txForm, fee: e.target.value })} style={{ width: '70px' }} />
            <input type="text" className="tx-note" placeholder="备注" value={txForm.note} onChange={(e) => setTxForm({ ...txForm, note: e.target.value })} />
            <button className={txForm.direction === 'buy' ? 'buy-btn' : 'sell-btn'} onClick={addTransaction}>
              {txForm.direction === 'buy' ? '确认买入' : '确认卖出'}
            </button>
          </div>

          {/* OCR transaction */}
          <div style={{ marginBottom: 8, fontSize: 13 }}>
            <label>OCR 识别交易截图：</label>
            <input type="file" accept="image/*" onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) ocrTransaction(f)
            }} />
          </div>

          {/* Transaction list */}
          {transactions.length > 0 && (
            <table className="tx-table">
              <thead>
                <tr>
                  <th>方向</th>
                  <th>日期</th>
                  <th>净值</th>
                  <th>份额</th>
                  <th>金额</th>
                  <th>手续费</th>
                  <th>备注</th>
                  <th>来源</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((tx) => (
                  <tr key={tx.id}>
                    <td style={{ color: tx.direction === 'buy' ? '#dc2626' : '#15803d' }}>
                      {tx.direction === 'buy' ? '买入' : '卖出'}
                    </td>
                    <td>{tx.trade_date}</td>
                    <td>{tx.nav}</td>
                    <td>{tx.shares}</td>
                    <td>{tx.amount}</td>
                    <td>{tx.fee !== '0' ? tx.fee : '-'}</td>
                    <td>{tx.note || '-'}</td>
                    <td>{tx.source}</td>
                    <td><button onClick={() => deleteTransaction(tx.id)}>删除</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {transactions.length === 0 && <p style={{ fontSize: 13, color: '#94a3b8' }}>暂无交易记录</p>}
        </section>
      )}

      {holdingsCode && (
        <section className="card">
          <h2>重仓股（前10） · {holdingsCode}</h2>
          {holdings.length === 0 ? (
            <p>暂无持仓数据</p>
          ) : (
            <div className="holdings-layout">
              <table className="holdings-table">
                <thead>
                  <tr>
                    <th>股票</th>
                    <th>占净值%</th>
                    <th>持仓市值(万)</th>
                  </tr>
                </thead>
                <tbody>
                  {holdings.map((h) => (
                    <tr key={h.stock_code}>
                      <td>{h.stock_name}({h.stock_code})</td>
                      <td>{h.percentage != null ? `${h.percentage}%` : '-'}</td>
                      <td>{h.value_wan != null ? h.value_wan.toLocaleString() : '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie
                    data={holdings.map((h) => ({ name: h.stock_name, value: h.percentage ?? 0 }))}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={90}
                    label={({ name, value }) => `${name} ${value}%`}
                  >
                    {holdings.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value: number) => `${value}%`} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </section>
      )}

      {pieData.length > 0 && (
        <section className="card">
          <h2>持仓分布</h2>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={pieData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={100}
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(1)}%`}
              >
                {pieData.map((_, i) => (
                  <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(value: number) => `¥${fmtAmount(value)}`} />
            </PieChart>
          </ResponsiveContainer>
        </section>
      )}

      {selectedCode && (
        <section className="card">
          <div className="section-header">
            <h2>趋势（最近 30 条） · {selectedCode}</h2>
            <div className="refresh-row">
              {lastRefresh && <span className="last-refresh">上次刷新: {lastRefresh}</span>}
              <button onClick={refreshData} disabled={refreshing}>
                {refreshing ? '刷新中...' : '刷新数据'}
              </button>
            </div>
          </div>
          {snapshots.length === 0 ? (
            <p>暂无快照数据，点击"刷新数据"拉取</p>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={snapshots} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis
                    dataKey="gztime"
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v: string) => v?.slice(11, 16) ?? ''}
                  />
                  <YAxis
                    yAxisId="left"
                    tick={{ fontSize: 11 }}
                    domain={['auto', 'auto']}
                    label={{ value: '估算净值', angle: -90, position: 'insideLeft', style: { fontSize: 11 } }}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    tick={{ fontSize: 11 }}
                    domain={['auto', 'auto']}
                    label={{ value: '涨跌幅%', angle: 90, position: 'insideRight', style: { fontSize: 11 } }}
                  />
                  <Tooltip
                    formatter={(value: number, name: string) =>
                      [name === '估算净值' ? value?.toFixed(4) : `${value?.toFixed(2)}%`, name]
                    }
                    labelFormatter={(label: string) => `时间: ${label}`}
                  />
                  <Legend />
                  <Line yAxisId="left" type="monotone" dataKey="gsz" name="估算净值" stroke="#2563eb" dot={false} strokeWidth={2} />
                  <Line yAxisId="right" type="monotone" dataKey="gszzl" name="涨跌幅%" stroke="#15803d" dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
              <p className="disclaimer">以上为盘中估算数据，非最终成交净值</p>
            </>
          )}
        </section>
      )}

      {msg && <p className="msg">{msg}</p>}
    </div>
  )
}

function fmtNum(v?: number | null) {
  if (v == null) return '-'
  return Number(v).toFixed(4)
}

function fmtAmount(v: number) {
  return v >= 10000 ? `${(v / 10000).toFixed(2)}万` : v.toFixed(2)
}

function fmtDecimal(v?: string | null, dp = 2) {
  if (v == null) return '-'
  try {
    return new Decimal(v).toFixed(dp)
  } catch {
    return v
  }
}

function pnlClass(v?: string | null) {
  if (v == null) return ''
  return Number(v) >= 0 ? 'up' : 'down'
}
