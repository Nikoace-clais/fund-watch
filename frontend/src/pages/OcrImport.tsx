import { useState, useRef, useCallback } from 'react'
import { Link } from 'react-router'
import {
  Camera,
  Upload,
  CheckCircle2,
  XCircle,
  Plus,
  Loader2,
  Image as ImageIcon,
  HelpCircle,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import { ocrFundCode, batchAddFunds, addFund } from '@/lib/api'
import { cn } from '@/lib/utils'

/* ---------- types ---------- */
type MatchedFund = {
  code: string
  name?: string
  amount?: number
  percentage?: number
}

type NameMatch = {
  code: string
  name: string
  matched_keyword: string
  type?: string
}

type OcrResult = {
  matched_codes: string[]
  matched_funds: MatchedFund[]
  name_matches: NameMatch[]
  raw_text: string
}

/* ---------- component ---------- */
export function OcrImport() {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [dragActive, setDragActive] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [preview, setPreview] = useState<string | null>(null)
  const [result, setResult] = useState<OcrResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [adding, setAdding] = useState(false)
  const [addResult, setAddResult] = useState<{ added: string[]; skipped: string[] } | null>(null)
  const [showGuide, setShowGuide] = useState(false)

  const reset = () => {
    setPreview(null)
    setResult(null)
    setError(null)
    setSelected(new Set())
    setAddResult(null)
  }

  const processFile = useCallback(async (file: File) => {
    if (!file.type.startsWith('image/')) {
      setError('请上传图片文件 (PNG/JPG/JPEG)')
      return
    }
    if (file.size > 10 * 1024 * 1024) {
      setError('文件大小不能超过 10MB')
      return
    }

    reset()
    setPreview(URL.createObjectURL(file))
    setUploading(true)

    try {
      const data = await ocrFundCode(file)
      setResult({
        matched_codes: data.matched_codes,
        matched_funds: data.matched_funds,
        name_matches: data.name_matches ?? [],
        raw_text: data.raw_text,
      })
      // auto-select all matched codes
      setSelected(new Set(data.matched_codes))
    } catch (e) {
      setError(e instanceof Error ? e.message : '识别失败，请重试')
    } finally {
      setUploading(false)
    }
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragActive(false)
      const file = e.dataTransfer.files[0]
      if (file) processFile(file)
    },
    [processFile],
  )

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) processFile(file)
    e.target.value = ''
  }

  const toggleCode = (code: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(code)) next.delete(code)
      else next.add(code)
      return next
    })
  }

  const toggleAll = () => {
    if (!result) return
    if (selected.size === result.matched_codes.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(result.matched_codes))
    }
  }

  const handleBatchAdd = async () => {
    const codes = Array.from(selected)
    if (codes.length === 0) return
    setAdding(true)
    try {
      if (codes.length === 1) {
        await addFund(codes[0])
        setAddResult({ added: codes, skipped: [] })
      } else {
        const data = await batchAddFunds(codes)
        setAddResult({ added: data.added, skipped: data.skipped })
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '添加失败')
    } finally {
      setAdding(false)
    }
  }

  const allCodes = result?.matched_codes ?? []
  const fundMap = new Map(
    (result?.matched_funds ?? []).map((f) => [f.code, f]),
  )
  const nameMatchMap = new Map(
    (result?.name_matches ?? []).map((n) => [n.code, n]),
  )
  const hasNameMatches = (result?.name_matches ?? []).length > 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">OCR 智能识别</h1>
        <p className="text-sm text-slate-500 mt-1">
          上传基金截图，自动识别基金代码并加入自选
        </p>
      </div>

      {/* Guide toggle */}
      <button
        onClick={() => setShowGuide((v) => !v)}
        className="inline-flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700 font-medium"
      >
        <HelpCircle className="h-4 w-4" />
        使用教程
        {showGuide ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
      </button>

      {/* Guide content */}
      {showGuide && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-6 space-y-4">
          <h3 className="text-base font-semibold text-blue-900">如何使用 OCR 识别功能</h3>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white rounded-lg p-4 border border-blue-100">
              <div className="flex items-center gap-2 mb-2">
                <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold">
                  1
                </span>
                <span className="font-medium text-slate-800">准备截图</span>
              </div>
              <p className="text-sm text-slate-600">
                在支付宝、天天基金、蛋卷基金等 App 中，截取你的基金持仓页面或基金详情页面。截图中包含
                <strong className="text-slate-800"> 6 位基金代码</strong>或
                <strong className="text-slate-800">基金名称</strong>均可识别。
              </p>
            </div>

            <div className="bg-white rounded-lg p-4 border border-blue-100">
              <div className="flex items-center gap-2 mb-2">
                <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold">
                  2
                </span>
                <span className="font-medium text-slate-800">上传图片</span>
              </div>
              <p className="text-sm text-slate-600">
                将截图拖拽到下方上传区域，或点击区域选择图片文件。支持
                <strong className="text-slate-800"> PNG / JPG / JPEG</strong> 格式，文件大小不超过 10MB。
              </p>
            </div>

            <div className="bg-white rounded-lg p-4 border border-blue-100">
              <div className="flex items-center gap-2 mb-2">
                <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold">
                  3
                </span>
                <span className="font-medium text-slate-800">确认添加</span>
              </div>
              <p className="text-sm text-slate-600">
                系统自动识别截图中的基金代码，勾选需要的基金后点击
                <strong className="text-slate-800">"加入自选"</strong>，即可批量添加到你的基金池。
              </p>
            </div>
          </div>

          <div className="bg-white rounded-lg p-4 border border-blue-100">
            <h4 className="text-sm font-semibold text-slate-700 mb-2">支持识别的内容</h4>
            <ul className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 text-sm text-slate-600">
              <li className="flex items-center gap-1.5">
                <CheckCircle2 className="h-3.5 w-3.5 text-green-500 flex-shrink-0" />
                支付宝/天天基金/蛋卷基金持仓截图
              </li>
              <li className="flex items-center gap-1.5">
                <CheckCircle2 className="h-3.5 w-3.5 text-green-500 flex-shrink-0" />
                基金详情页截图（含基金代码）
              </li>
              <li className="flex items-center gap-1.5">
                <CheckCircle2 className="h-3.5 w-3.5 text-green-500 flex-shrink-0" />
                基金推荐文章中的基金列表截图
              </li>
              <li className="flex items-center gap-1.5">
                <CheckCircle2 className="h-3.5 w-3.5 text-green-500 flex-shrink-0" />
                任意包含 6 位基金代码的图片
              </li>
              <li className="flex items-center gap-1.5">
                <CheckCircle2 className="h-3.5 w-3.5 text-green-500 flex-shrink-0" />
                仅含基金名称的截图（自动反查基金代码）
              </li>
            </ul>
          </div>

          <p className="text-xs text-blue-700">
            提示：图片越清晰，识别准确率越高。建议使用原图而非压缩后的图片。即使截图中没有基金代码，只要包含基金名称，系统也会尝试自动反查对应代码。
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Upload area */}
        <div className="space-y-4">
          <div
            onDragOver={(e) => {
              e.preventDefault()
              setDragActive(true)
            }}
            onDragLeave={() => setDragActive(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={cn(
              'relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-10 cursor-pointer transition-all',
              dragActive
                ? 'border-blue-500 bg-blue-50'
                : 'border-slate-300 bg-white hover:border-blue-400 hover:bg-slate-50',
              uploading && 'pointer-events-none opacity-60',
            )}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleFileChange}
              className="hidden"
            />

            {uploading ? (
              <>
                <Loader2 className="h-10 w-10 text-blue-500 animate-spin mb-3" />
                <p className="text-sm text-slate-500">正在识别中...</p>
              </>
            ) : (
              <>
                <div className="rounded-full bg-blue-50 p-4 mb-4">
                  <Upload className="h-8 w-8 text-blue-500" />
                </div>
                <p className="text-sm font-medium text-slate-700 mb-1">
                  拖拽图片到此处，或点击上传
                </p>
                <p className="text-xs text-slate-400">
                  支持 PNG / JPG / JPEG，不超过 10MB
                </p>
              </>
            )}
          </div>

          {/* Image preview */}
          {preview && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
                <div className="flex items-center gap-2 text-sm text-slate-600">
                  <ImageIcon className="h-4 w-4" />
                  上传图片预览
                </div>
                <button
                  onClick={reset}
                  className="text-xs text-slate-400 hover:text-red-500"
                >
                  清除
                </button>
              </div>
              <div className="p-4">
                <img
                  src={preview}
                  alt="OCR preview"
                  className="max-h-80 w-full object-contain rounded-lg"
                />
              </div>
            </div>
          )}
        </div>

        {/* Results area */}
        <div className="space-y-4">
          {/* Error */}
          {error && (
            <div className="flex items-center gap-2 bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
              <XCircle className="h-4 w-4 flex-shrink-0" />
              {error}
            </div>
          )}

          {/* Add result */}
          {addResult && (
            <div className="bg-green-50 border border-green-200 rounded-lg px-4 py-3 text-sm">
              <div className="flex items-center gap-2 text-green-700 font-medium mb-1">
                <CheckCircle2 className="h-4 w-4" />
                批量添加完成
              </div>
              {addResult.added.length > 0 && (
                <p className="text-green-600">
                  已添加: {addResult.added.join('、')}
                </p>
              )}
              {addResult.skipped.length > 0 && (
                <p className="text-slate-500">
                  已存在(跳过): {addResult.skipped.join('、')}
                </p>
              )}
              <Link
                to="/portfolio"
                className="inline-flex items-center gap-1 text-blue-600 hover:underline mt-2 text-xs font-medium"
              >
                查看自选基金 →
              </Link>
            </div>
          )}

          {/* Matched codes */}
          {result && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
              <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-slate-800">
                  识别结果
                  <span className="ml-2 text-xs font-normal text-slate-400">
                    共识别到 {allCodes.length} 个基金
                    {hasNameMatches && '（通过名称匹配）'}
                  </span>
                </h3>
                {allCodes.length > 0 && (
                  <button
                    onClick={toggleAll}
                    className="text-xs text-blue-600 hover:text-blue-700"
                  >
                    {selected.size === allCodes.length ? '取消全选' : '全选'}
                  </button>
                )}
              </div>

              {allCodes.length === 0 ? (
                <div className="px-4 py-8 text-center text-slate-400 text-sm">
                  <Camera className="h-8 w-8 mx-auto mb-2 text-slate-300" />
                  未识别到基金代码或基金名称，请确认图片中包含基金相关信息
                </div>
              ) : (
                <>
                  <div className="divide-y divide-slate-100">
                    {allCodes.map((code) => {
                      const fund = fundMap.get(code)
                      const nameMatch = nameMatchMap.get(code)
                      const displayName = fund?.name || nameMatch?.name || ''
                      return (
                        <label
                          key={code}
                          className={cn(
                            'flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors',
                            selected.has(code) ? 'bg-blue-50/50' : 'hover:bg-slate-50',
                          )}
                        >
                          <input
                            type="checkbox"
                            checked={selected.has(code)}
                            onChange={() => toggleCode(code)}
                            className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                          />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-sm font-mono font-medium text-blue-600">
                                {code}
                              </span>
                              {displayName && (
                                <span className="text-sm text-slate-700 truncate">
                                  {displayName}
                                </span>
                              )}
                              {nameMatch && (
                                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-50 text-amber-700 border border-amber-200">
                                  名称匹配
                                </span>
                              )}
                            </div>
                            <div className="flex gap-3 text-xs text-slate-400 mt-0.5 flex-wrap">
                              {fund?.amount != null && (
                                <span>金额: ¥{fund.amount.toLocaleString()}</span>
                              )}
                              {fund?.percentage != null && (
                                <span>占比: {fund.percentage}%</span>
                              )}
                              {nameMatch && (
                                <span>匹配关键词: {nameMatch.matched_keyword}</span>
                              )}
                              {nameMatch?.type && (
                                <span>类型: {nameMatch.type}</span>
                              )}
                            </div>
                          </div>
                          <Link
                            to={`/funds/${code}`}
                            onClick={(e) => e.stopPropagation()}
                            className="text-xs text-slate-400 hover:text-blue-600"
                          >
                            详情 →
                          </Link>
                        </label>
                      )
                    })}
                  </div>

                  <div className="px-4 py-3 border-t border-slate-100 flex items-center justify-between">
                    <span className="text-xs text-slate-400">
                      已选择 {selected.size} / {allCodes.length}
                    </span>
                    <button
                      onClick={handleBatchAdd}
                      disabled={selected.size === 0 || adding}
                      className={cn(
                        'inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium transition-colors',
                        selected.size > 0
                          ? 'bg-blue-600 text-white hover:bg-blue-700 shadow-sm'
                          : 'bg-slate-100 text-slate-400 cursor-not-allowed',
                      )}
                    >
                      {adding ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Plus className="h-4 w-4" />
                      )}
                      加入自选
                    </button>
                  </div>
                </>
              )}
            </div>
          )}

          {/* Raw text (collapsible) */}
          {result && result.raw_text && (
            <details className="bg-white rounded-xl border border-slate-200 shadow-sm">
              <summary className="px-4 py-3 text-sm font-medium text-slate-600 cursor-pointer hover:text-slate-800">
                查看 OCR 原始文本
              </summary>
              <div className="px-4 pb-4">
                <pre className="text-xs text-slate-500 bg-slate-50 rounded-lg p-3 whitespace-pre-wrap break-all max-h-48 overflow-y-auto">
                  {result.raw_text}
                </pre>
              </div>
            </details>
          )}

          {/* Empty state when no upload yet */}
          {!result && !uploading && !error && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col items-center justify-center py-16 text-center">
              <Camera className="h-12 w-12 text-slate-300 mb-3" />
              <p className="text-sm text-slate-400 mb-1">上传截图后，识别结果将显示在这里</p>
              <p className="text-xs text-slate-300">支持批量识别多个基金代码</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
