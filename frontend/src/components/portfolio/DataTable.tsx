import { flexRender, type Table } from '@tanstack/react-table'
import { cn } from '@/lib/utils'

/** 渲染 TanStack Table 实例的通用表格;name/select 列左对齐,actions 居中,其余右对齐 */
export function DataTable<T>({ table, cellPadding = 'px-4' }: { table: Table<T>; cellPadding?: string }) {
  const alignClass = (columnId: string) =>
    cn(
      columnId === 'name' || columnId === 'select' ? 'text-left' : 'text-right',
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
          {table.getRowModel().rows.map((row) => (
            <tr
              key={row.id}
              className={cn('transition-colors', row.getIsSelected() ? 'bg-blue-50' : 'hover:bg-slate-50')}
            >
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id} className={cn(cellPadding, 'py-3', alignClass(cell.column.id))}>
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
