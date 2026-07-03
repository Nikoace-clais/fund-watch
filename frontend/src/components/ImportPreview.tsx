import { useState, useMemo, type DragEvent, type ChangeEvent, type FC } from 'react';
import { Upload, FileImage, AlertCircle, KeyRound, Loader2 } from 'lucide-react';
import type { ImportPreviewResult, OcrStep } from '../services/import';
import { previewImport, confirmImport, HIGH_CONFIDENCE, MEDIUM_CONFIDENCE } from '../services/import';
import { Checkbox } from './Checkbox';
import { ErrorBanner } from './PageState';
import { ImportRow } from './import/ImportRow';
import { OcrProgress } from './import/OcrProgress';
import { useOcrStatus, usePortfolios } from '@/lib/queries';
import { useProviderConfig } from '@/lib/provider-config';

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
          .filter((f) => f.confidence >= HIGH_CONFIDENCE)
          .map((f) => f.code)
      );
    }
    return new Set();
  });
  const [isConfirming, setIsConfirming] = useState(false);
  // Portfolio selection for import
  const { data: portfolios = [] } = usePortfolios();
  const { config: providerConfig, isConfigured } = useProviderConfig();
  const { data: ocrStatus } = useOcrStatus();
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
        result.funds.filter((f) => f.confidence >= HIGH_CONFIDENCE).map((f) => f.code)
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
    const highConfidence = preview.funds.filter((f) => f.confidence >= HIGH_CONFIDENCE).length;
    const mediumConfidence = preview.funds.filter(
      (f) => f.confidence >= MEDIUM_CONFIDENCE && f.confidence < HIGH_CONFIDENCE
    ).length;
    const lowConfidence = preview.funds.filter((f) => f.confidence < MEDIUM_CONFIDENCE).length;

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
                  <Checkbox
                    checked={selectedCodes.size === totalCount && totalCount > 0}
                    indeterminate={selectedCodes.size > 0 && selectedCodes.size < totalCount}
                    onChange={toggleSelectAll}
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

      {error && <ErrorBanner className="mt-4">{error}</ErrorBanner>}
    </div>
  );
};

export default ImportPreview;
