import { useState, useMemo, type DragEvent, type ChangeEvent, type FC } from 'react';
import { Upload, FileImage, AlertCircle, CheckCircle2, Loader2, KeyRound } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import type { ImportPreviewResult, ImportPreviewItem, OcrStep } from '../services/import';
import { previewImport, confirmImport, formatConfidence, getConfidenceInfo } from '../services/import';
import { usePortfolios } from '@/lib/queries';
import { useProviderConfig } from '@/lib/provider-config';
import { getOcrStatus } from '@/lib/api';

interface ImportPreviewProps {
  onImport?: (codes: string[]) => void;
  initialData?: ImportPreviewResult;
}

export const ImportPreview: FC<ImportPreviewProps> = ({
  onImport,
  initialData,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [currentStep, setCurrentStep] = useState<OcrStep | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<ImportPreviewResult | null>(initialData || null);
  const [selectedCodes, setSelectedCodes] = useState<Set<string>>(() => {
    // Auto-select high confidence funds
    if (initialData) {
      return new Set(
        initialData.funds
          .filter((f) => f.confidence >= 0.85)
          .map((f) => f.code)
      );
    }
    return new Set();
  });
  const [isConfirming, setIsConfirming] = useState(false);
  // Portfolio selection for import
  const { data: portfolios = [] } = usePortfolios();
  const { config: providerConfig, isConfigured } = useProviderConfig();
  const { data: ocrStatus } = useQuery({
    queryKey: ['ocr-status'],
    queryFn: getOcrStatus,
    refetchInterval: (q) => (q.state.data?.ready ? false : 2000),
  });
  const ocrReady = ocrStatus?.ready ?? false;
  // 'new' = create new portfolio, or a number = existing portfolio id
  const [importTarget, setImportTarget] = useState<'new' | number>('new');
  const [newPfName, setNewPfName] = useState('');

  const handleDragOver = (e: DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = async (e: DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const imgs = Array.from(e.dataTransfer.files).filter((f) => f.type.startsWith('image/'));
    if (imgs.length) await processFiles(imgs);
  };

  const handleFileSelect = async (e: ChangeEvent<HTMLInputElement>) => {
    const imgs = Array.from(e.target.files || []);
    if (imgs.length) await processFiles(imgs);
  };

  const processFiles = async (imgs: File[]) => {
    setIsLoading(true);
    setError(null);

    try {
      const result = await previewImport(
        imgs,
        isConfigured ? providerConfig : undefined,
        setCurrentStep,
      );
      setCurrentStep(null);
      setPreview(result);
      // Auto-select high confidence funds
      const autoSelected = new Set(
        result.funds.filter((f) => f.confidence >= 0.85).map((f) => f.code)
      );
      setSelectedCodes(autoSelected);
    } catch (err) {
      setCurrentStep(null);
      setError(err instanceof Error ? err.message : '处理失败');
    } finally {
      setIsLoading(false);
    }
  };

  const toggleSelection = (code: string) => {
    setSelectedCodes((prev) => {
      const next = new Set(prev);
      if (next.has(code)) {
        next.delete(code);
      } else {
        next.add(code);
      }
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (!preview) return;

    if (selectedCodes.size === preview.funds.length) {
      setSelectedCodes(new Set());
    } else {
      setSelectedCodes(new Set(preview.funds.map((f) => f.code)));
    }
  };

  const handleConfirm = async () => {
    if (selectedCodes.size === 0) return;

    setIsConfirming(true);
    try {
      const items = (preview?.funds ?? [])
        .filter((f) => selectedCodes.has(f.code))
        .map((f) => ({ code: f.code, amount: f.amount }));
      const opts = importTarget === 'new'
        ? { portfolioName: newPfName.trim() || undefined }
        : { portfolioId: importTarget };
      const result = await confirmImport(items, opts);
      if (result.success) {
        onImport?.(items.map((i) => i.code));
        setPreview(null);
        setSelectedCodes(new Set());
        setNewPfName('');
        setImportTarget('new');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '导入失败');
    } finally {
      setIsConfirming(false);
    }
  };

  const handleReset = () => {
    setPreview(null);
    setSelectedCodes(new Set());
    setError(null);
  };

  const selectedCount = selectedCodes.size;
  const totalCount = preview?.funds.length || 0;

  // Calculate stats
  const stats = useMemo(() => {
    if (!preview) return null;
    const highConfidence = preview.funds.filter((f) => f.confidence >= 0.85).length;
    const mediumConfidence = preview.funds.filter(
      (f) => f.confidence >= 0.75 && f.confidence < 0.85
    ).length;
    const lowConfidence = preview.funds.filter((f) => f.confidence < 0.75).length;

    return { highConfidence, mediumConfidence, lowConfidence };
  }, [preview]);

  if (isLoading) {
    return <OcrProgress currentStep={currentStep} />;
  }

  if (preview) {
    return (
      <div className="space-y-4">
        {/* Header Stats */}
        <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg">
          <div className="flex items-center space-x-4">
            <span className="text-sm text-slate-600">
              识别到 <strong className="text-slate-900">{totalCount}</strong> 个基金
            </span>
            {stats && (
              <div className="flex items-center space-x-2 text-xs">
                <span className="px-2 py-1 bg-green-100 text-green-800 rounded">
                  高置信度: {stats.highConfidence}
                </span>
                <span className="px-2 py-1 bg-yellow-100 text-yellow-800 rounded">
                  中置信度: {stats.mediumConfidence}
                </span>
                <span className="px-2 py-1 bg-red-100 text-red-800 rounded">
                  需确认: {stats.lowConfidence}
                </span>
              </div>
            )}
          </div>
          <button
            onClick={handleReset}
            className="text-sm text-slate-500 hover:text-slate-700"
          >
            重新上传
          </button>
        </div>

        {/* Warning for low confidence */}
        {preview.needs_review && (
          <div className="flex items-center p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
            <AlertCircle className="w-5 h-5 text-yellow-600 mr-2" />
            <span className="text-sm text-yellow-800">
              部分基金置信度较低，请仔细核对后勾选
            </span>
          </div>
        )}

        {/* Results Table */}
        <div className="border rounded-lg overflow-hidden">
          <table className="w-full">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-4 py-3 text-left">
                  <input
                    type="checkbox"
                    checked={selectedCodes.size === totalCount && totalCount > 0}
                    onChange={toggleSelectAll}
                    className="rounded border-slate-300"
                    data-testid="select-all"
                  />
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium text-slate-700">
                  基金名称
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium text-slate-700">
                  基金代码
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium text-slate-700">
                  类型
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium text-slate-700">
                  持有金额
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium text-slate-700">
                  置信度
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium text-slate-700">
                  状态
                </th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {preview.funds.map((fund) => (
                <ImportRow
                  key={fund.code}
                  fund={fund}
                  isSelected={selectedCodes.has(fund.code)}
                  onToggle={() => toggleSelection(fund.code)}
                />
              ))}
            </tbody>
          </table>
        </div>

        {/* Portfolio selection */}
        <div className="border-t border-slate-100 pt-4 mt-2">
          <p className="text-sm font-medium text-slate-700 mb-2">导入到组合</p>
          <div className="flex flex-wrap gap-2 mb-3">
            <button
              type="button"
              onClick={() => setImportTarget('new')}
              className={`px-3 py-1 rounded-lg text-xs font-medium border transition-colors ${importTarget === 'new' ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-slate-600 border-slate-200 hover:border-blue-300'}`}
            >
              新建组合
            </button>
            {portfolios.map((pf) => (
              <button
                key={pf.id}
                type="button"
                onClick={() => setImportTarget(pf.id)}
                className={`px-3 py-1 rounded-lg text-xs font-medium border transition-colors ${importTarget === pf.id ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-slate-600 border-slate-200 hover:border-blue-300'}`}
              >
                {pf.name}
              </button>
            ))}
          </div>
          {importTarget === 'new' && (
            <input
              type="text"
              value={newPfName}
              onChange={(e) => setNewPfName(e.target.value)}
              placeholder={`组合名称（留空则自动生成）`}
              className="w-full border border-slate-200 rounded-lg px-3 py-1.5 text-sm outline-none focus:border-blue-400"
            />
          )}
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-between pt-4">
          <div className="text-sm text-slate-600">
            已选择 <strong className="text-slate-900">{selectedCount}</strong> 个基金
          </div>
          <div className="flex space-x-3">
            <button
              onClick={handleReset}
              className="px-4 py-2 text-slate-600 hover:text-slate-800"
            >
              取消
            </button>
            <button
              onClick={handleConfirm}
              disabled={selectedCount === 0 || isConfirming}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
            >
              {isConfirming ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  导入中...
                </>
              ) : (
                `确认导入 (${selectedCount})`
              )}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`relative border-2 border-dashed rounded-xl p-12 text-center transition-colors ${
        isDragging
          ? 'border-blue-500 bg-blue-50'
          : 'border-slate-300 hover:border-slate-400'
      }`}
    >
      <input
        type="file"
        accept="image/png,image/jpeg,image/jpg,image/webp"
        multiple
        onChange={handleFileSelect}
        className="hidden"
        id="import-file"
        data-testid="file-input"
      />
      <label
        htmlFor="import-file"
        className="flex flex-col items-center cursor-pointer"
      >
        <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mb-4">
          {isDragging ? (
            <Upload className="w-8 h-8 text-blue-600" />
          ) : (
            <FileImage className="w-8 h-8 text-blue-600" />
          )}
        </div>
        <h3 className="text-lg font-medium text-slate-900 mb-2">上传截图</h3>
        <p className="text-sm text-slate-500 mb-4">
          支持 PNG、JPG、WebP，可同时选多张，自动去重
        </p>
        <span className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
          选择文件
        </span>
      </label>

      {!ocrReady && (
        <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg flex items-center">
          <Loader2 className="w-4 h-4 text-blue-500 mr-2 shrink-0 animate-spin" />
          <span className="text-sm text-blue-800">
            OCR 模型初始化中，首次启动需下载模型文件，请稍候...
          </span>
        </div>
      )}

      {!isConfigured && (
        <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-lg flex items-center">
          <KeyRound className="w-4 h-4 text-amber-600 mr-2 shrink-0" />
          <span className="text-sm text-amber-800">
            未配置 AI 密钥，识别将使用服务器默认配置（如无则失败）。可在{' '}
            <a href="/ai-select" className="underline font-medium">AI 选基</a>{' '}
            页面右上角配置。
          </span>
        </div>
      )}

      {error && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center">
          <AlertCircle className="w-5 h-5 text-red-600 mr-2" />
          <span className="text-sm text-red-800">{error}</span>
        </div>
      )}
    </div>
  );
};

interface ImportRowProps {
  fund: ImportPreviewItem;
  isSelected: boolean;
  onToggle: () => void;
}

const ImportRow: FC<ImportRowProps> = ({ fund, isSelected, onToggle }) => {
  const ci = getConfidenceInfo(fund.confidence);

  return (
    <tr
      className={`hover:bg-slate-50 ${fund.needs_review ? 'bg-yellow-50/30' : ''}`}
    >
      <td className="px-4 py-3">
        <input
          type="checkbox"
          checked={isSelected}
          onChange={onToggle}
          className="rounded border-slate-300"
        />
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center">
          <span className="font-medium text-slate-900">{fund.name}</span>
          {fund.needs_review && (
            <AlertCircle className="w-4 h-4 text-yellow-500 ml-2" />
          )}
        </div>
        {fund.ocr_name && fund.ocr_name !== fund.name && (
          <div className="text-xs text-amber-600 mt-0.5">
            识别: {fund.ocr_name}
            {fund.similarity != null && (
              <span className="text-slate-400 ml-1">({Math.round(fund.similarity * 100)}%)</span>
            )}
          </div>
        )}
      </td>
      <td className="px-4 py-3 text-sm font-mono text-slate-600">{fund.code}</td>
      <td className="px-4 py-3 text-sm text-slate-600">{fund.type}</td>
      <td className="px-4 py-3 text-sm text-slate-600">
        {fund.amount != null && fund.amount > 0
          ? `¥${fund.amount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
          : <span className="text-slate-300">—</span>}
      </td>
      <td className="px-4 py-3">
        <span className={`text-sm font-medium ${ci.color}`}>
          {formatConfidence(fund.confidence)}
        </span>
      </td>
      <td className="px-4 py-3 space-y-1">
        <span className={`inline-flex items-center px-2 py-1 text-xs rounded-full ${ci.className}`}>
          {fund.needs_review ? (
            <><AlertCircle className="w-3 h-3 mr-1" />{ci.label}</>
          ) : (
            <><CheckCircle2 className="w-3 h-3 mr-1" />{ci.label}</>
          )}
        </span>
        {fund.review === 'confirmed' && (
          <span className="block text-xs text-green-600">✓ Pro已确认</span>
        )}
        {fund.review === 'corrected' && fund.ocr_name && (
          <span className="block text-xs text-amber-600" title={`OCR识别: ${fund.ocr_name}`}>
            ✎ Pro已修正
          </span>
        )}
      </td>
    </tr>
  );
};

const STEPS: { key: OcrStep['step']; label: string }[] = [
  { key: 'ocr',          label: '识别图片文字' },
  { key: 'ai_extract',   label: 'AI 提取基金名称' },
  { key: 'search',       label: '搜索基金数据库' },
  { key: 'pro_identify', label: 'Pro 识别未命中基金' },
  { key: 'pro_review',   label: 'Pro 核查匹配结果' },
];

const OcrProgress: FC<{ currentStep: OcrStep | null }> = ({ currentStep }) => {
  const activeIdx = currentStep
    ? STEPS.findIndex((s) => s.key === currentStep.step)
    : 0;

  return (
    <div className="flex flex-col items-center justify-center p-10 space-y-6">
      <Loader2 className="w-10 h-10 text-blue-500 animate-spin" />
      <p className="text-sm font-medium text-slate-700">
        {currentStep?.text ?? '准备中...'}
      </p>
      <ol className="w-full max-w-xs space-y-2">
        {STEPS.map((s, i) => {
          const done = i < activeIdx;
          const active = i === activeIdx && !!currentStep;
          return (
            <li key={s.key} className="flex items-center gap-2 text-sm">
              {done ? (
                <CheckCircle2 className="w-4 h-4 text-green-500 shrink-0" />
              ) : active ? (
                <Loader2 className="w-4 h-4 text-blue-500 animate-spin shrink-0" />
              ) : (
                <span className="w-4 h-4 rounded-full border border-slate-300 shrink-0" />
              )}
              <span className={done ? 'text-slate-400 line-through' : active ? 'text-slate-900 font-medium' : 'text-slate-400'}>
                {s.label}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
};

export default ImportPreview;
