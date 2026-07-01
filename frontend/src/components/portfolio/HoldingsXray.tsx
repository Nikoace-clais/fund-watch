import { Fragment, useMemo, useState } from 'react'
import { flexRender, useReactTable, getCoreRowModel, getSortedRowModel, createColumnHelper, type SortingState } from '@tanstack/react-table'
import { ChevronDown, ChevronRight } from 'lucide-react'
import type { HoldingXraySector, HoldingXrayStock, PortfolioHoldings } from '@/lib/api'
import { cn, formatCNY } from '@/lib/utils'
import { SortHead } from './SortHead'

// ponytail: 横向堆叠条够用，要交互式饼图再说
const SECTOR_COLORS = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16']

type DisplaySector = { name: string; weight_pct: number }

function buildDisplay(sectors: HoldingXraySector[]): DisplaySector[] {
  const main = sectors.filter((s) => s.weight_pct >= 0.05)
  const otherPct = sectors.filter((s) => s.weight_pct < 0.05).reduce((sum, s) => sum + s.weight_pct, 0)
  return otherPct > 0 ? [...main, { name: '其他', weight_pct: otherPct }] : main
}

function SectorBar({
  sectors,
  selected,
  onSelect,
}: {
  sectors: HoldingXraySector[]
  selected: string | null
  onSelect: (name: string | null) => void
}) {
  if (!sectors.length) return null
  const display = buildDisplay(sectors)
  const total = display.reduce((sum, s) => sum + s.weight_pct, 0) || 1
  return (
    <div className="mt-3">
      <div className="flex h-3 rounded overflow-hidden gap-px">
        {display.map((s, i) => (
          <div
            key={s.name}
            role="button"
            onClick={() => onSelect(selected === s.name ? null : s.name)}
            style={{ width: `${(s.weight_pct / total) * 100}%`, backgroundColor: SECTOR_COLORS[i % SECTOR_COLORS.length] }}
            title={`${s.name} ${s.weight_pct.toFixed(1)}%`}
            className={cn('cursor-pointer transition-opacity', selected && selected !== s.name && 'opacity-25')}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1.5">
        {display.map((s, i) => (
          <button
            key={s.name}
            onClick={() => onSelect(selected === s.name ? null : s.name)}
            className={cn(
              'flex items-center gap-1 text-xs transition-opacity',
              selected && selected !== s.name ? 'opacity-30' : 'text-slate-500',
              selected === s.name && 'font-medium text-slate-700',
            )}
          >
            <span className="inline-block h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: SECTOR_COLORS[i % SECTOR_COLORS.length] }} />
            {s.name} {s.weight_pct.toFixed(1)}%
          </button>
        ))}
      </div>
    </div>
  )
}

const helper = createColumnHelper<HoldingXrayStock>()

function ExpandedFunds({ stock }: { stock: HoldingXrayStock }) {
  return (
    <div className="px-4 py-2 bg-amber-50 border-t border-amber-100 space-y-1">
      {stock.funds.map((f) => (
        <div key={f.code} className="flex items-center justify-between text-xs text-slate-600">
          <span className="font-medium">{f.name} <span className="text-slate-400">({f.code})</span></span>
          <span>占净值 {f.percentage?.toFixed(2) ?? '--'}% · 暴露 {formatCNY(parseFloat(f.contribution))}</span>
        </div>
      ))}
    </div>
  )
}

export function HoldingsXray({ data }: { data: PortfolioHoldings }) {
  const [sorting, setSorting] = useState<SortingState>([{ id: 'exposure', desc: true }])
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [selectedSector, setSelectedSector] = useState<string | null>(null)

  // Main sector names (those not collapsed into "其他")
  const mainSectorNames = useMemo(
    () => new Set((data.sectors ?? []).filter((s) => s.weight_pct >= 0.05).map((s) => s.name)),
    [data.sectors],
  )

  const filteredStocks = useMemo(() => {
    if (!selectedSector) return data.stocks
    return data.stocks.filter((s) => {
      const ind = s.industry ?? '未分类'
      if (selectedSector === '其他') return !mainSectorNames.has(ind)
      return ind === selectedSector
    })
  }, [data.stocks, selectedSector, mainSectorNames])

  const toggle = (code: string) =>
    setExpanded((prev) => {
      const next = new Set(prev)
      next.has(code) ? next.delete(code) : next.add(code)
      return next
    })

  const coveragePct =
    parseFloat(data.total_value) > 0
      ? ((parseFloat(data.covered_value) / parseFloat(data.total_value)) * 100).toFixed(1)
      : null

  const columns = useMemo(
    () => [
      helper.display({
        id: 'expand',
        size: 32,
        header: () => null,
        cell: ({ row }) => {
          const s = row.original
          if (s.fund_count < 2) return null
          const open = expanded.has(s.stock_code)
          return (
            <button onClick={() => toggle(s.stock_code)} className="text-amber-500 hover:text-amber-700 transition-colors">
              {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
            </button>
          )
        },
      }),
      helper.accessor((row) => row.stock_name, {
        id: 'name',
        header: ({ column }) => <SortHead column={column}>股票</SortHead>,
        cell: ({ row }) => {
          const s = row.original
          return (
            <div>
              <p className="font-medium text-slate-900 leading-snug">{s.stock_name}</p>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className="text-xs text-slate-400">{s.stock_code}</span>
                {s.industry && (
                  <span className="inline-block px-1 py-0.5 rounded text-xs bg-slate-100 text-slate-500">
                    {s.industry}
                  </span>
                )}
              </div>
            </div>
          )
        },
        sortingFn: (a, b) => a.original.stock_name.localeCompare(b.original.stock_name, 'zh-CN'),
      }),
      helper.accessor((row) => parseFloat(row.exposure), {
        id: 'exposure',
        size: 130,
        header: ({ column }) => (
          <SortHead column={column} right tooltip="组合中对该股票的估算暴露金额（各基金市值×持仓占比之和）">暴露金额</SortHead>
        ),
        cell: ({ row }) => (
          <p className="text-right text-slate-800">{formatCNY(parseFloat(row.original.exposure))}</p>
        ),
      }),
      helper.accessor('weight_pct', {
        size: 90,
        header: ({ column }) => (
          <SortHead column={column} right tooltip="暴露金额占组合总市值的比例">组合占比</SortHead>
        ),
        cell: ({ row }) => (
          <p className="text-right text-slate-600">{row.original.weight_pct.toFixed(2)}%</p>
        ),
      }),
      helper.accessor('fund_count', {
        size: 90,
        header: ({ column }) => (
          <SortHead column={column} right tooltip="持有该股票的基金数量；≥2 表示重叠持仓">基金数</SortHead>
        ),
        cell: ({ row }) => {
          const n = row.original.fund_count
          return (
            <div className="text-right">
              {n >= 2 ? (
                <span className="inline-block px-1.5 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-700">
                  {n} 只 重叠
                </span>
              ) : (
                <span className="text-slate-400 text-sm">{n}</span>
              )}
            </div>
          )
        },
      }),
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [expanded],
  )

  const table = useReactTable({
    data: filteredStocks,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getRowId: (row) => row.stock_code,
    sortDescFirst: true,
    ...({ sortUndefined: 'last' } as object),
  })

  const overlapCount = data.stocks.filter((s) => s.fund_count >= 2).length

  const alignOf = (id: string) =>
    id === 'name' || id === 'expand' ? 'text-left' : 'text-right'

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-100">
        <h2 className="text-lg font-semibold text-slate-800">持仓穿透</h2>
        <p className="text-xs text-slate-400 mt-0.5">
          基于各基金前十大重仓
          {coveragePct && <>，约覆盖 <span className="font-medium text-slate-500">{coveragePct}%</span> 组合市值</>}
          {overlapCount > 0 && (
            <span className="ml-2 text-amber-600 font-medium">· {overlapCount} 只股票重叠持仓</span>
          )}
        </p>
        <SectorBar sectors={data.sectors ?? []} selected={selectedSector} onSelect={setSelectedSector} />
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <colgroup>
            {table.getVisibleLeafColumns().map((col) => (
              <col key={col.id} style={col.id !== 'name' ? { width: `${col.getSize()}px` } : undefined} />
            ))}
          </colgroup>
          <thead>
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id} className="bg-slate-50 text-slate-500 text-xs uppercase">
                {hg.headers.map((h) => (
                  <th key={h.id} className={cn('px-4 py-3 align-middle', alignOf(h.column.id))}>
                    {h.isPlaceholder ? null : flexRender(h.column.columnDef.header, h.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-slate-100">
            {table.getRowModel().rows.map((row) => {
              const s = row.original
              const overlap = s.fund_count >= 2
              const open = expanded.has(s.stock_code)
              return (
                <Fragment key={row.id}>
                  <tr className={cn('transition-colors hover:bg-slate-50', overlap && 'bg-amber-50/30')}>
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className={cn('px-4 py-3', alignOf(cell.column.id))}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                  {open && (
                    <tr>
                      <td colSpan={columns.length} className="p-0">
                        <ExpandedFunds stock={s} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
