import { useState } from 'react'
import { Link } from 'react-router'
import { Sparkles, ExternalLink, Plus, Loader2, AlertCircle } from 'lucide-react'
import { fetchAiSectors, aiSelectFunds, batchAddFunds } from '@/lib/api'
import type { AiFundRec } from '@/lib/api'
import { useQuery } from '@tanstack/react-query'
import { useInvalidatePortfolio } from '@/lib/queries'
import { useProviderConfig } from '@/lib/provider-config'
import { cn } from '@/lib/utils'
import { useColor } from '@/lib/color-context'

const EMPHASIS_OPTIONS = [
  { value: '稳健低回撤', label: '稳健低回撤', desc: '追求波动小、回撤控制好' },
  { value: '进攻高收益', label: '进攻高收益', desc: '追求长期高弹性收益' },
  { value: '低费率', label: '低费率', desc: '降低买入成本' },
  { value: '老将经理', label: '老将经理', desc: '偏好经验丰富的基金经理' },
]

function RecCard({ rec, onAdd }: { rec: AiFundRec; onAdd: (code: string) => Promise<void> }) {
  const { colorFor } = useColor()
  const [adding, setAdding] = useState(false)
  const [added, setAdded] = useState(false)

  async function handleAdd() {
    setAdding(true)
    try {
      await onAdd(rec.code)
      setAdded(true)
    } finally {
      setAdding(false)
    }
  }

  const fmt = (v: number | null, suffix = '%') =>
    v != null ? `${v.toFixed(2)}${suffix}` : '--'

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-3">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <span className="shrink-0 w-7 h-7 flex items-center justify-center rounded-full bg-blue-600 text-white text-sm font-bold">
            {rec.rank}
          </span>
          <div className="min-w-0">
            <p className="font-semibold text-slate-900 truncate">{rec.name || rec.code}</p>
            <p className="text-xs text-slate-400 font-mono">{rec.code}</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <Link
            to={`/funds/${rec.code}`}
            className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50 transition-colors"
          >
            详情 <ExternalLink className="h-3 w-3" />
          </Link>
          <button
            onClick={handleAdd}
            disabled={adding || added}
            className={cn(
              'inline-flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-lg transition-colors',
              added
                ? 'bg-green-50 text-green-700 border border-green-200 cursor-default'
                : 'bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-60',
            )}
          >
            {adding ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" />}
            {added ? '已加入' : '加入自选'}
          </button>
        </div>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
        <Metric label="近1年" value={fmt(rec.one_year_return)} className={colorFor(rec.one_year_return ?? 0)} />
        <Metric label="近3年" value={fmt(rec.three_year_return)} className={colorFor(rec.three_year_return ?? 0)} />
        <Metric label="最大回撤" value={rec.max_drawdown != null ? `-${fmt(rec.max_drawdown)}` : '--'} className="text-amber-600" />
        <Metric label="申购费率" value={rec.fee ?? '--'} />
      </div>

      {/* Manager / Size */}
      {(rec.manager || rec.size != null) && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
          {rec.manager && <span>经理：<span className="text-slate-700">{rec.manager}</span></span>}
          {rec.size != null && <span>规模：<span className="text-slate-700">{rec.size.toFixed(2)} 亿</span></span>}
        </div>
      )}

      {/* AI reasoning */}
      <p className="text-sm text-slate-600 leading-relaxed border-t border-slate-100 pt-3">{rec.reason}</p>
    </div>
  )
}

function Metric({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div className="bg-slate-50 rounded-lg px-2 py-2">
      <p className="text-[10px] text-slate-400 mb-0.5">{label}</p>
      <p className={cn('text-sm font-semibold tabular-nums', className ?? 'text-slate-900')}>{value}</p>
    </div>
  )
}

export function AiSelect() {
  const invalidatePortfolio = useInvalidatePortfolio()
  const { config: providerConfig, isConfigured } = useProviderConfig()
  const { data: sectorsData } = useQuery({
    queryKey: ['ai', 'sectors'],
    queryFn: fetchAiSectors,
    select: (r) => r.sectors,
    staleTime: Infinity,
  })
  const sectors = sectorsData ?? []

  const [theme, setTheme] = useState('')
  const [emphasis, setEmphasis] = useState(EMPHASIS_OPTIONS[0].value)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<{ summary: string; recommendations: AiFundRec[] } | null>(null)

  async function handleSelect() {
    if (!theme) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await aiSelectFunds(theme, emphasis, {
        provider: providerConfig.provider,
        api_key: providerConfig.api_key || undefined,
        base_url: providerConfig.base_url || undefined,
        model: providerConfig.model || undefined,
      })
      setResult(res)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'AI 选基失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  async function handleAdd(code: string) {
    await batchAddFunds([code])
    invalidatePortfolio()
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <Sparkles className="h-6 w-6 text-blue-600" />
          AI 选基
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          选择板块和着重点，AI 从真实数据中为你发现候选、排序、点评
        </p>
      </div>

      {/* Unconfigured warning */}
      {!isConfigured && (
        <div className="flex items-center gap-2 px-4 py-3 bg-amber-50 border border-amber-200 rounded-xl text-sm text-amber-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          尚未配置 API Key。请点击左侧导航底部的「AI 配置」完成设置后再使用。
        </div>
      )}

      {/* Form card */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-5">
        {/* Theme selector */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">板块 / 主题</label>
          <select
            value={theme}
            onChange={(e) => setTheme(e.target.value)}
            className="w-full px-3 py-2.5 rounded-lg border border-slate-200 bg-white text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="">请选择板块…</option>
            {sectors.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>

        {/* Emphasis selector */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">着重点</label>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {EMPHASIS_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setEmphasis(opt.value)}
                className={cn(
                  'flex flex-col items-start p-3 rounded-lg border text-left transition-colors text-sm',
                  emphasis === opt.value
                    ? 'border-blue-500 bg-blue-50 text-blue-700'
                    : 'border-slate-200 hover:border-slate-300 text-slate-700',
                )}
              >
                <span className="font-medium">{opt.label}</span>
                <span className="text-[11px] mt-0.5 opacity-70">{opt.desc}</span>
              </button>
            ))}
          </div>
        </div>

        <button
          onClick={handleSelect}
          disabled={!theme || loading}
          className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-2.5 rounded-lg bg-blue-600 text-white font-medium text-sm hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              AI 分析中，约 10-30 秒…
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" />
              开始 AI 选基
            </>
          )}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-start gap-2 px-4 py-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
          <div>
            <p className="font-medium">选基失败</p>
            <p className="mt-0.5 opacity-80">{error}</p>
          </div>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-4">
          {/* AI summary */}
          <div className="bg-blue-50 border border-blue-200 rounded-xl px-5 py-4">
            <p className="text-xs font-medium text-blue-600 mb-1.5 flex items-center gap-1">
              <Sparkles className="h-3 w-3" /> AI 总体评述
            </p>
            <p className="text-sm text-slate-700 leading-relaxed">{result.summary}</p>
          </div>

          {/* Recommendation cards */}
          <div className="space-y-4">
            {result.recommendations.map((rec) => (
              <RecCard key={rec.code} rec={rec} onAdd={handleAdd} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
