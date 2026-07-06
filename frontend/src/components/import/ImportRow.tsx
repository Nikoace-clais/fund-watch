import type { FC } from 'react';
import { AlertCircle, CheckCircle2 } from 'lucide-react';
import type { ImportPreviewItem } from '@/services/import';
import { formatConfidence, getConfidenceInfo } from '@/services/import';
import { formatNum2 } from '@/lib/utils';
import { Checkbox } from '../Checkbox';

interface ImportRowProps {
  fund: ImportPreviewItem;
  isSelected: boolean;
  onToggle: () => void;
}

export const ImportRow: FC<ImportRowProps> = ({ fund, isSelected, onToggle }) => {
  const ci = getConfidenceInfo(fund.confidence);

  return (
    <tr
      className={`hover:bg-slate-50 ${fund.needs_review ? 'bg-yellow-50/30' : ''}`}
    >
      <td className="px-4 py-3">
        <Checkbox checked={isSelected} onChange={onToggle} />
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
          ? `¥${formatNum2(fund.amount)}`
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
