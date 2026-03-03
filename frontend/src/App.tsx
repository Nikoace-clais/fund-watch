import { useEffect, useMemo, useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'

type FundOverview = {
  fund: {
    code: string
    name?: string | null
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

type OcrResp = {
  matched_codes: string[]
  raw_text: string
}

type Snapshot = {
  captured_at: string
  gsz?: number | null
  gszzl?: number | null
  gztime?: string | null
}

const API = 'http://127.0.0.1:8010'

export function App() {
  const [funds, setFunds] = useState<FundOverview[]>([])
  const [ocrCodes, setOcrCodes] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [msg, setMsg] = useState('')
  const [manualCode, setManualCode] = useState('')
  const [selectedCode, setSelectedCode] = useState<string | null>(null)
  const [snapshots, setSnapshots] = useState<Snapshot[]>([])

  const dedupedCodes = useMemo(() => Array.from(new Set(ocrCodes)), [ocrCodes])

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
    const res = await fetch(`${API}/api/snapshots/${code}?limit=30`)
    const data = await res.json()
    const items: Snapshot[] = data.items ?? []
    setSnapshots(items.reverse())
  }

  async function onUpload(file: File) {
    setLoading(true)
    setMsg('')
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(`${API}/api/ocr/fund-code`, { method: 'POST', body: form })
      if (!res.ok) throw new Error('OCR 请求失败')
      const data: OcrResp = await res.json()
      const filtered = (data.matched_codes || []).filter((c) => /^\d{6}$/.test(c))
      const invalidCount = (data.matched_codes || []).length - filtered.length
      setOcrCodes(filtered)
      setMsg(`识别完成：${filtered.join(', ') || '未识别到基金代码'}${invalidCount > 0 ? `（过滤无效 ${invalidCount} 条）` : ''}`)
    } catch (e) {
      setMsg(e instanceof Error ? e.message : '上传失败')
    } finally {
      setLoading(false)
    }
  }

  async function addFund(code: string) {
    setMsg('')
    const res = await fetch(`${API}/api/funds/${code}`, { method: 'POST' })
    if (!res.ok) {
      setMsg(`添加 ${code} 失败`)
      return
    }
    await loadFunds()
    setMsg(`已加入基金池：${code}`)
  }

  async function addFundManual() {
    const code = manualCode.trim()
    if (!/^\d{6}$/.test(code)) {
      setMsg('请输入 6 位基金代码')
      return
    }
    await addFund(code)
    setManualCode('')
  }

  async function addAllOcrCodes() {
    if (dedupedCodes.length === 0) return
    const res = await fetch(`${API}/api/funds/batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codes: dedupedCodes }),
    })
    if (!res.ok) {
      setMsg('批量加入失败')
      return
    }
    const data = await res.json()
    await loadFunds()
    setMsg(`批量加入完成：${(data.added || []).join(', ') || '无新增'}${(data.invalid || []).length ? `；无效：${data.invalid.join(',')}` : ''}`)
  }

  return (
    <div className="page">
      <h1>Fund Watch · 最小前端</h1>
      <p>上传截图 → OCR识别基金编号 → 一键加入基金池 → 查看估算净值/趋势</p>

      <section className="card">
        <h2>手动添加基金</h2>
        <div className="row">
          <input value={manualCode} placeholder="输入 6 位代码，如 161725" onChange={(e) => setManualCode(e.target.value)} />
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
        {dedupedCodes.length > 0 && (
          <>
            <div className="chips">
              {dedupedCodes.map((c) => (
                <button key={c} onClick={() => addFund(c)}>
                  加入 {c}
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
        <h2>基金池（含最新估算）</h2>
        {funds.length === 0 ? (
          <p>暂无基金</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>代码</th>
                <th>名称</th>
                <th>估算净值</th>
                <th>估算涨跌%</th>
                <th>时间</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {funds.map((f) => (
                <tr key={f.fund.code}>
                  <td>{f.fund.code}</td>
                  <td>{f.latest?.name || '-'}</td>
                  <td>{fmtNum(f.latest?.gsz)}</td>
                  <td className={Number(f.latest?.gszzl || 0) >= 0 ? 'up' : 'down'}>{fmtNum(f.latest?.gszzl)}</td>
                  <td>{f.latest?.gztime || '-'}</td>
                  <td>
                    <button onClick={() => loadSnapshots(f.fund.code)}>看趋势</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {selectedCode && (
        <section className="card">
          <h2>趋势（最近 30 条） · {selectedCode}</h2>
          {snapshots.length === 0 ? (
            <p>暂无快照数据</p>
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
