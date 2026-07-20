import { useState } from 'react'
import { Link } from 'react-router'
import { Sparkles, ExternalLink, Plus, Loader2 } from 'lucide-react'
import { ErrorBanner } from '@/components/PageState'
import { streamAiSelect } from '@/lib/api'
import type { AiFundRec } from '@/lib/api'
import { useBatchAddFunds } from '@/lib/queries'
import { useSelectedPortfolio } from '@/lib/portfolio-context'
import { useProviderConfig } from '@/lib/provider-config'
import { cn } from '@/lib/utils'
import { useColor } from '@/lib/color-context'

const EMPHASIS_OPTIONS = [
  { value: '稳健低回撤', label: '稳健低回撤', desc: '追求波动小、回撤控制好' },
  { value: '进攻高收益', label: '进攻高收益', desc: '追求长期高弹性收益' },
  { value: '低费率', label: '低费率', desc: '降低买入成本' },
  { value: '老将经理', label: '老将经理', desc: '偏好经验丰富的基金经理' },
]

// ponytail: 静态分组，合并了相近板块（医疗/医药、芯片/半导体、光伏/新能源等）
// 被合并的词仍可通过下方自由输入框命中后端子串匹配
const SECTOR_GROUPS = [
  { group: '消费医药', items: ['白酒', '食品饮料', '消费', '医药', '农业'] },
  {
    group: '科技成长',
    items: ['半导体', '科技', '互联网', '传媒', '新能源', '汽车'],
  },
  {
    group: '金融周期',
    items: [
      '银行',
      '证券',
      '金融',
      '地产',
      '煤炭',
      '钢铁',
      '有色',
      '化工',
      '电力',
    ],
  },
  { group: '主题策略', items: ['军工', '环保', '养老', '红利'] },
  {
    group: '宽基指数',
    items: ['沪深300', '中证500', '中证1000', '创业板', '科创'],
  },
  { group: '海外 / QDII', items: ['港股', '纳斯达克', '标普', 'QDII'] },
  { group: '固收 / 货币', items: ['债', '货币'] },
]

function RecCard({
  rec,
  onAdd,
}: {
  rec: AiFundRec
  onAdd: (code: string) => Promise<void>
}) {
  const { colorFor } = useColor()
  const [adding, setAdding] = useState(false)
  const [added, setAdded] = useState(false)
  const [addError, setAddError] = useState(false)

  async function handleAdd() {
    setAdding(true)
    setAddError(false) // 重试时先清除上次的错误提示
    try {
      await onAdd(rec.code)
      setAdded(true)
    } catch {
      // 失败提示 3 秒后自动消失
      setAddError(true)
      setTimeout(() => setAddError(false), 3000)
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
            <p className="font-semibold text-slate-900 truncate">
              {rec.name || rec.code}
            </p>
            <p className="text-xs text-slate-400 font-mono">{rec.code}</p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          <div className="flex items-center gap-1.5">
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
              {adding ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Plus className="h-3 w-3" />
              )}
              {added ? '已加入' : '加入自选'}
            </button>
          </div>
          {addError && <p className="text-xs text-red-600">添加失败，请重试</p>}
        </div>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
        <Metric
          label="近1年"
          value={fmt(rec.one_year_return)}
          className={colorFor(rec.one_year_return ?? 0)}
        />
        <Metric
          label="近3年"
          value={fmt(rec.three_year_return)}
          className={colorFor(rec.three_year_return ?? 0)}
        />
        <Metric
          label="最大回撤"
          value={rec.max_drawdown != null ? `-${fmt(rec.max_drawdown)}` : '--'}
          className="text-amber-600"
        />
        <Metric label="申购费率" value={rec.fee ?? '--'} />
      </div>

      {/* Manager / Size */}
      {(rec.manager || rec.size != null) && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
          {rec.manager && (
            <span>
              经理：<span className="text-slate-700">{rec.manager}</span>
            </span>
          )}
          {rec.size != null && (
            <span>
              规模：
              <span className="text-slate-700">{rec.size.toFixed(2)} 亿</span>
            </span>
          )}
        </div>
      )}

      {/* AI reasoning */}
      <p className="text-sm text-slate-600 leading-relaxed border-t border-slate-100 pt-3">
        {rec.reason}
      </p>
    </div>
  )
}

function Metric({
  label,
  value,
  className,
}: {
  label: string
  value: string
  className?: string
}) {
  return (
    <div className="bg-slate-50 rounded-lg px-2 py-2">
      <p className="text-[10px] text-slate-400 mb-0.5">{label}</p>
      <p
        className={cn(
          'text-sm font-semibold tabular-nums',
          className ?? 'text-slate-900',
        )}
      >
        {value}
      </p>
    </div>
  )
}

export function AiSelect() {
  const { selectedId } = useSelectedPortfolio()
  const batchAddFunds = useBatchAddFunds(selectedId)
  const { config: providerConfig, isConfigured } = useProviderConfig()

  const [theme, setTheme] = useState('')
  const [emphasis, setEmphasis] = useState(EMPHASIS_OPTIONS[0].value)
  const [loading, setLoading] = useState(false)
  const [steps, setSteps] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<{
    summary: string
    recommendations: AiFundRec[]
  } | null>(null)

  async function handleSelect() {
    if (!theme) return
    setLoading(true)
    setSteps([])
    setError(null)
    setResult(null)
    await streamAiSelect(
      theme,
      emphasis,
      {
        provider: providerConfig.provider,
        api_key: providerConfig.api_key || undefined,
        base_url: providerConfig.base_url || undefined,
        model: providerConfig.model || undefined,
        analysis_model: providerConfig.analysis_model || undefined,
      },
      {
        onStep: (text) => setSteps((prev) => [...prev, text]),
        onResult: (data) => {
          setResult(data)
          setSteps([])
        },
        onError: (text) => setError(text),
      },
    )
    setLoading(false)
  }

  async function handleAdd(code: string) {
    await batchAddFunds.mutateAsync({
      codes: [code],
      opts: selectedId != null ? { portfolioId: selectedId } : undefined,
    })
  }

  function handleReset() {
    setResult(null)
    setError(null)
  }

  const collapsed = loading || !!result

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
        <ErrorBanner variant="warning">
          尚未配置 API Key。请点击左侧导航底部的「AI 配置」完成设置后再使用。
        </ErrorBanner>
      )}

      {/* Form card — collapsed to summary strip while loading/showing results */}
      {collapsed ? (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm px-5 py-3 flex items-center justify-between gap-4">
          <div className="text-sm text-slate-600 min-w-0">
            <span className="text-slate-400">板块：</span>
            <span className="font-medium text-slate-800 inline-block max-w-full truncate align-bottom">
              {theme}
            </span>
            <span className="mx-2 text-slate-300">·</span>
            <span className="text-slate-400">着重点：</span>
            <span className="font-medium text-slate-800">{emphasis}</span>
          </div>
          {loading ? (
            <div className="flex items-center gap-1.5 shrink-0 text-sm text-blue-600">
              <Loader2 className="h-4 w-4 animate-spin" />
              分析中…
            </div>
          ) : (
            <button
              onClick={handleReset}
              className="shrink-0 text-sm text-slate-500 hover:text-slate-800 transition-colors"
            >
              重新选择
            </button>
          )}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-5">
          {/* Theme selector */}
          <div className="space-y-3">
            <label
              htmlFor="custom-theme"
              className="block text-sm font-medium text-slate-700"
            >
              板块 / 主题
            </label>
            {SECTOR_GROUPS.map(({ group, items }) => (
              <div key={group}>
                <p className="text-[11px] text-slate-400 font-medium mb-1.5 uppercase tracking-wide">
                  {group}
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {items.map((item) => (
                    <button
                      key={item}
                      type="button"
                      onClick={() => setTheme(theme === item ? '' : item)}
                      className={cn(
                        'px-3 py-1 rounded-full text-sm border transition-colors',
                        theme === item
                          ? 'border-blue-500 bg-blue-50 text-blue-700 font-medium'
                          : 'border-slate-200 text-slate-600 hover:border-slate-300 hover:bg-slate-50',
                      )}
                    >
                      {item}
                    </button>
                  ))}
                </div>
              </div>
            ))}
            <input
              id="custom-theme"
              value={theme}
              onChange={(e) => setTheme(e.target.value)}
              placeholder="或输入自定义主题，如：人工智能、黄金、医疗…"
              className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* Emphasis selector */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              着重点
            </label>
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
                  <span className="text-[11px] mt-0.5 opacity-70">
                    {opt.desc}
                  </span>
                </button>
              ))}
            </div>
          </div>

          <button
            onClick={handleSelect}
            disabled={!theme || loading}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-2.5 rounded-lg bg-blue-600 text-white font-medium text-sm hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Sparkles className="h-4 w-4" />
            开始 AI 选基
          </button>
        </div>
      )}

      {/* Progress steps */}
      {loading && steps.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 space-y-2 max-h-60 overflow-y-auto">
          {steps.map((s, i) => (
            <div
              key={i}
              className="flex items-center gap-2 text-sm text-slate-600"
            >
              <span className="text-green-500 shrink-0">✓</span>
              <span>{s}</span>
            </div>
          ))}
          <div className="flex items-center gap-2 text-sm text-blue-600">
            <Loader2 className="h-4 w-4 animate-spin shrink-0" />
            <span>分析中…</span>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <ErrorBanner className="items-start [&>svg]:mt-0.5">
          <p className="font-medium">选基失败</p>
          <p className="mt-0.5 opacity-80">{error}</p>
        </ErrorBanner>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-4">
          {/* AI summary */}
          <div className="bg-blue-50 border border-blue-200 rounded-xl px-5 py-4">
            <p className="text-xs font-medium text-blue-600 mb-1.5 flex items-center gap-1">
              <Sparkles className="h-3 w-3" /> AI 总体评述
            </p>
            <p className="text-sm text-slate-700 leading-relaxed">
              {result.summary}
            </p>
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
