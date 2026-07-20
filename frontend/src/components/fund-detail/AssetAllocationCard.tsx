import { useMemo } from 'react'
import {
  PieChart as RechartsPieChart,
  Pie,
  Cell,
  Legend,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { PieChart } from 'lucide-react'
import type { FundDetailData } from '@/lib/api'
import { CHART_COLORS as PIE_COLORS } from '@/lib/utils'

function simplifyAssetName(name: string) {
  if (name.includes('股票')) return '股票'
  if (name.includes('债券')) return '债券'
  if (name.includes('现金')) return '现金'
  if (name.includes('基金')) return '基金'
  // strip "占净比" etc.
  return name.replace(/占净比/g, '').trim()
}

export function AssetAllocationCard({ detail }: { detail: FundDetailData }) {
  const assetData = useMemo(
    () =>
      detail.asset_allocation
        .filter((a) => a.value > 0)
        .map((a) => ({ name: simplifyAssetName(a.name), value: a.value })),
    [detail],
  )

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
      <div className="flex items-center gap-2 mb-4">
        <PieChart className="h-5 w-5 text-slate-600" />
        <h2 className="text-lg font-semibold text-slate-800">资产配置</h2>
      </div>
      {assetData.length === 0 ? (
        <div className="flex items-center justify-center h-[200px] text-slate-400 text-sm">
          暂无配置数据
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={240}>
          {/* margin.top 给饼图外侧 label 留出空间，否则顶部标签会被裁掉 */}
          <RechartsPieChart
            margin={{ top: 24, right: 12, bottom: 4, left: 12 }}
          >
            <Pie
              data={assetData}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              innerRadius={45}
              outerRadius={70}
              paddingAngle={2}
              label={({ name, value }) => `${name} ${value.toFixed(1)}%`}
            >
              {assetData.map((_, i) => (
                <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip formatter={(value: number) => `${value.toFixed(2)}%`} />
            <Legend />
          </RechartsPieChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
