import React, { useState, useCallback, useMemo } from 'react';
import { Upload, FileImage, AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ImportPreviewResult, ImportPreviewItem } from '../services/import';
import {
  previewImport,
  confirmImport,
  formatConfidence,
  getConfidenceColor,
  getConfidenceBadge,
} from '../services/import';

interface ImportPreviewProps {
  onImport?: (codes: string[]) => void;
  initialData?: ImportPreviewResult;
}

export const ImportPreview: React.FC<ImportPreviewProps> = ({
  onImport,
  initialData,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
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

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    async (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);

      const file = e.dataTransfer.files[0];
      if (file && file.type.startsWith('image/')) {
        await processFile(file);
      }
    },
    []
  );

  const handleFileSelect = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        await processFile(file);
      }
    },
    []
  );

  const processFile = async (file: File) => {
    setIsLoading(true);
    setError(null);

    try {
      const result = await previewImport(file);
      setPreview(result);
      // Auto-select high confidence funds
      const autoSelected = new Set(
        result.funds.filter((f) => f.confidence >= 0.85).map((f) => f.code)
      );
      setSelectedCodes(autoSelected);
    } catch (err) {
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
      const codes = Array.from(selectedCodes);
      const result = await confirmImport(codes);
      if (result.success) {
        onImport?.(codes);
        // Reset state
        setPreview(null);
        setSelectedCodes(new Set());
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
    return (
      <div className="flex flex-col items-center justify-center p-12 space-y-4">
        <Loader2 className="w-12 h-12 text-blue-500 animate-spin" />
        <p className="text-slate-600">正在识别截图中的基金...</p>
      </div>
    );
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
          支持 PNG、JPG、WebP 格式，最大 10MB
        </p>
        <span className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
          选择文件
        </span>
      </label>

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

const ImportRow: React.FC<ImportRowProps> = ({ fund, isSelected, onToggle }) => {
  const badge = getConfidenceBadge(fund.confidence);

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
      </td>
      <td className="px-4 py-3 text-sm font-mono text-slate-600">{fund.code}</td>
      <td className="px-4 py-3 text-sm text-slate-600">{fund.type}</td>
      <td className="px-4 py-3">
        <span className={`text-sm font-medium ${getConfidenceColor(fund.confidence)}`}>
          {formatConfidence(fund.confidence)}
        </span>
      </td>
      <td className="px-4 py-3">
        <span className={`inline-flex items-center px-2 py-1 text-xs rounded-full ${badge.className}`}>
          {fund.needs_review ? (
            <>
              <AlertCircle className="w-3 h-3 mr-1" />
              {badge.label}
            </>
          ) : (
            <>
              <CheckCircle2 className="w-3 h-3 mr-1" />
              {badge.label}
            </>
          )}
        </span>
      </td>
    </tr>
  );
};

export default ImportPreview;
