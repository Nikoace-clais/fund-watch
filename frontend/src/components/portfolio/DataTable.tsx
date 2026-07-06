import { Fragment, type ReactNode } from 'react'
import { flexRender, type Row, type Table } from '@tanstack/react-table'
import { cn } from '@/lib/utils'

const LEFT_ALIGN_IDS = new Set(['name', 'select', 'expand'])

/** 渲染 TanStack Table 实例的通用表格;name/select/expand 列左对齐,actions 居中,其余右对齐。
 * renderSubRow 可选,用于在每行下方插入展开内容(如 HoldingsXray 的重叠持仓明细)。 */
export function DataTable<T>({
  table,
  cellPadding = 'px-4',
  rowClassName,
  renderSubRow,
}: {
  table: Table<T>
  cellPadding?: string
  rowClassName?: (row: Row<T>) => string | undefined
  renderSubRow?: (row: Row<T>) => ReactNode
}) {
  const alignClass = (columnId: string) =>
    cn(
      LEFT_ALIGN_IDS.has(columnId) ? 'text-left' : 'text-right',
      columnId === 'actions' && 'text-center',
    )

  return (
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
              {hg.headers.map((header) => (
                <th key={header.id} className={cn(cellPadding, 'py-3 align-middle', alignClass(header.column.id))}>
                  {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody className="divide-y divide-slate-100">
          {table.getRowModel().rows.map((row) => {
            const tr = (
              <tr
                key={renderSubRow ? undefined : row.id}
                className={cn(
                  'transition-colors',
                  rowClassName?.(row),
                  row.getIsSelected() ? 'bg-blue-50' : 'hover:bg-slate-50',
                )}
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className={cn(cellPadding, 'py-3', alignClass(cell.column.id))}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            )
            if (!renderSubRow) return tr
            return (
              <Fragment key={row.id}>
                {tr}
                {renderSubRow(row)}
              </Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
