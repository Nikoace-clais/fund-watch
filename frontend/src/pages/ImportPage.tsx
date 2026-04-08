import React, { useState } from 'react';
import { ImportPreview } from '../components/ImportPreview';
import { ArrowLeft, CheckCircle2 } from 'lucide-react';

interface ImportPageProps {
  onBack?: () => void;
}

export const ImportPage: React.FC<ImportPageProps> = ({ onBack }) => {
  const [importSuccess, setImportSuccess] = useState(false);
  const [importedCount, setImportedCount] = useState(0);

  const handleImport = (codes: string[]) => {
    setImportedCount(codes.length);
    setImportSuccess(true);
  };

  const handleReset = () => {
    setImportSuccess(false);
    setImportedCount(0);
  };

  if (importSuccess) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <div className="text-center py-12">
          <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
            <CheckCircle2 className="w-10 h-10 text-green-600" />
          </div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">导入成功！</h2>
          <p className="text-gray-600 mb-8">
            已成功导入 <strong>{importedCount}</strong> 个基金到您的基金池
          </p>
          <div className="flex justify-center space-x-4">
            <button
              onClick={handleReset}
              className="px-6 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
            >
              继续导入
            </button>
            <button
              onClick={onBack}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              查看基金池
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      {/* Header */}
      <div className="flex items-center mb-6">
        {onBack && (
          <button
            onClick={onBack}
            className="mr-4 p-2 hover:bg-gray-100 rounded-lg"
          >
            <ArrowLeft className="w-5 h-5 text-gray-600" />
          </button>
        )}
        <div>
          <h1 className="text-2xl font-bold text-gray-900">截图导入基金</h1>
          <p className="text-sm text-gray-500 mt-1">
            上传持仓截图，自动识别基金代码和名称
          </p>
        </div>
      </div>

      {/* Import Component */}
      <div className="bg-white rounded-xl shadow-sm border p-6">
        <ImportPreview onImport={handleImport} />
      </div>

      {/* Tips */}
      <div className="mt-6 p-4 bg-blue-50 rounded-lg">
        <h3 className="text-sm font-medium text-blue-900 mb-2">💡 使用提示</h3>
        <ul className="text-sm text-blue-800 space-y-1 list-disc list-inside">
          <li>支持支付宝、天天基金、券商 APP 等持仓截图</li>
          <li>截图建议包含基金名称和代码信息</li>
          <li>置信度低于 75% 的结果需要人工确认</li>
          <li>AI 辅助识别接口已预留，未来支持更智能的识别</li>
        </ul>
      </div>
    </div>
  );
};

export default ImportPage;
