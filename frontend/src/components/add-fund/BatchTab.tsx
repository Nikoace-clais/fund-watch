import { useState } from 'react'
import { Check, AlertCircle, ChevronDown, ChevronUp, Copy } from 'lucide-react'
import { useBatchAddFunds } from '@/lib/queries'
import { parseBatchInput } from '@/lib/parse-batch-input'
import { cn } from '@/lib/utils'

const AI_PROMPT = `请识别这张截图中的所有基金持仓信息，按以下 JSON 格式输出：

{"funds": [
  {
    "code": "6位基金代码",
    "name": "基金名称",
    "holding_amount": 持仓金额（数字，单位元），
    "cumulative_return": 累计收益（数字，单位元，亏损为负数），
    "holding_return": 持有收益（数字，单位元，亏损为负数）
  }
]}

注意事项：
- code 和 name 尽量都填，系统会自动交叉验证；只有名称没有代码也可以
- name 填写截图中显示的完整基金名称
- 金额字段若截图中没有，可省略该字段
- 所有金额为纯数字，不带"元"或"¥"符号
- 亏损的收益填写负数，例如 -123.45`

const PLACEHOLDER = `{"funds": [
  {"code": "110011", "name": "易方达优质精选混合", "holding_amount": 10000.5, "cumulative_return": 500.25, "holding_return": 300.1},
  {"name": "招商中证白酒指数", "holding_amount": 5000}
]}

也支持旧格式：{"codes": ["110011"]}
或每行一个代码：110011`

export function BatchTab({ portfolioId }: { portfolioId?: number }) {
  const [text, setText] = useState('')
  const [result, setResult] = useState<{ added: string[]; invalid: string[]; warnings: string[] } | null>(null)
  const [error, setError] = useState('')
  const batchAddFunds = useBatchAddFunds(portfolioId)
  const loading = batchAddFunds.isPending

  const handleImport = () => {
    setError('')
    setResult(null)
    const { codes, funds } = parseBatchInput(text)
    if (codes.length === 0 && funds.length === 0) {
      setError('未识别到有效的6位基金代码')
      return
    }
    batchAddFunds.mutate(
      { codes, funds, opts: { portfolioId } },
      {
        onSuccess: (data) => setResult({ added: data.added, invalid: data.invalid ?? [], warnings: data.warnings ?? [] }),
        onError: (err: Error) => setError(err.message || '导入失败'),
      },
    )
  }

  const [showPrompt, setShowPrompt] = useState(false)
  const [copied, setCopied] = useState(false)

  const handleCopyPrompt = () => {
    navigator.clipboard.writeText(AI_PROMPT).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="space-y-4">
      {/* AI prompt helper */}
      <div className="rounded-lg border border-blue-200 bg-blue-50 overflow-hidden">
        <button
          type="button"
          onClick={() => setShowPrompt((v) => !v)}
          className="w-full flex items-center justify-between px-4 py-2.5 text-sm font-medium text-blue-700 hover:bg-blue-100 transition-colors"
        >
          <span>用 AI 识别截图？先复制提示词</span>
          {showPrompt ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
        {showPrompt && (
          <div className="px-4 pb-3">
            <pre className="text-xs text-slate-600 whitespace-pre-wrap bg-white rounded border border-blue-100 p-3 mb-2 leading-relaxed">
              {AI_PROMPT}
            </pre>
            <button
              type="button"
              onClick={handleCopyPrompt}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
                copied
                  ? 'bg-green-100 text-green-700'
                  : 'bg-white border border-blue-200 text-blue-600 hover:bg-blue-50'
              )}
            >
              {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? '已复制' : '复制提示词'}
            </button>
          </div>
        )}
      </div>

      <div>
        <label className="block text-sm font-medium text-slate-600 mb-1.5">粘贴基金数据</label>
        <textarea
          value={text}
          onChange={(e) => {
            setText(e.target.value)
            setResult(null)
            setError('')
          }}
          rows={7}
          placeholder={PLACEHOLDER}
          className="w-full px-4 py-3 border border-slate-200 rounded-lg text-sm font-mono resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
        <p className="mt-1.5 text-xs text-slate-400">
          支持含持仓金额/累计收益/持有收益的 JSON，或旧格式 codes 数组，或纯代码列表
        </p>
      </div>

      <button
        onClick={handleImport}
        disabled={!text.trim() || loading}
        className={cn(
          'w-full py-2.5 rounded-lg text-sm font-medium transition-colors',
          text.trim() && !loading
            ? 'bg-blue-600 text-white hover:bg-blue-700'
            : 'bg-slate-100 text-slate-400 cursor-not-allowed'
        )}
      >
        {loading ? '导入中...' : '导入'}
      </button>

      {error && (
        <div className="flex items-center gap-2 text-sm text-red-500 px-3 py-2.5 bg-red-50 rounded-lg">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-2 text-sm">
          {result.added.length > 0 && (
            <div className="flex items-start gap-2 px-3 py-2.5 bg-green-50 text-green-700 rounded-lg">
              <Check className="w-4 h-4 shrink-0 mt-0.5" />
              <span>成功添加 {result.added.length} 只：{result.added.join(', ')}</span>
            </div>
          )}
          {result.invalid.length > 0 && (
            <div className="flex items-start gap-2 px-3 py-2.5 bg-slate-50 text-slate-500 rounded-lg">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>无法识别 {result.invalid.length} 项：{result.invalid.join(', ')}</span>
            </div>
          )}
          {result.warnings.length > 0 && (
            <div className="flex items-start gap-2 px-3 py-2.5 bg-amber-50 text-amber-700 rounded-lg">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div className="space-y-1">
                {result.warnings.map((w, i) => <p key={i}>{w}</p>)}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
