import React, { useState } from 'react';
import { ImportPreview } from '../components/ImportPreview';
import { CheckCircle2, Camera, Lightbulb } from 'lucide-react';
import { useNavigate } from 'react-router';
import { cn } from '@/lib/utils';

export const ImportPage: React.FC = () => {
  const navigate = useNavigate();
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
      <div className="max-w-4xl mx-auto">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-12 text-center">
          <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
            <CheckCircle2 className="w-10 h-10 text-green-600" />
          </div>
          <h2 className="text-2xl font-bold text-slate-900 mb-2">导入成功！</h2>
          <p className="text-slate-600 mb-8">
            已成功导入 <strong className="text-slate-900">{importedCount}</strong> 个基金到您的基金池
          </p>
          <div className="flex justify-center space-x-4">
            <button
              onClick={handleReset}
              className="px-6 py-2.5 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 font-medium transition-colors"
            >
              继续导入
            </button>
            <button
              onClick={() => navigate('/portfolio')}
              className="px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium transition-colors"
            >
              查看基金池
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-3">
            <Camera className="w-7 h-7 text-blue-600" />
            截图导入基金
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            上传持仓截图，自动识别基金代码和名称
          </p>
        </div>
      </div>

      {/* Import Component */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <ImportPreview onImport={handleImport} />
      </div>

      {/* Tips */}
      <div className={cn(
        "rounded-xl p-5",
        "bg-gradient-to-r from-blue-50 to-indigo-50",
        "border border-blue-100"
      )}>
        <div className="flex items-start gap-3">
          <Lightbulb className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" />
          <div>
            <h3 className="text-sm font-semibold text-blue-900 mb-2">使用提示</h3>
            <ul className="text-sm text-blue-800 space-y-1.5">
              <li className="flex items-center gap-2">
                <span className="w-1 h-1 bg-blue-400 rounded-full"></span>
                支持支付宝、天天基金、券商 APP 等持仓截图
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1 h-1 bg-blue-400 rounded-full"></span>
                截图建议包含基金名称和代码信息
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1 h-1 bg-blue-400 rounded-full"></span>
                置信度低于 75% 的结果需要人工确认
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1 h-1 bg-blue-400 rounded-full"></span>
                AI 辅助识别接口已预留，未来支持更智能的识别
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ImportPage;
