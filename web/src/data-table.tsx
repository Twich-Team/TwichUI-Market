import { Loading } from "./loading";
import { Fragment, ReactNode, useEffect, useId, useMemo, useState } from "react";
import {
  ColumnDef,
  type Table,
  OnChangeFn,
  PaginationState,
  SortingState,
  VisibilityState,
  ColumnFiltersState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { Menu } from "@base-ui/react/menu";
export function ColumnMenu<T>({table,closeAfterChange=false}:{table:Table<T>;closeAfterChange?:boolean}) {
  const [open,setOpen]=useState(false);
  return <Menu.Root open={open} onOpenChange={setOpen}>
          <Menu.Trigger className="column-menu-trigger">Columns</Menu.Trigger>
          <Menu.Portal>
            <Menu.Positioner sideOffset={6}>
              <Menu.Popup className="table-menu">
                {table
                  .getAllLeafColumns()
                  .filter((c) => c.getCanHide())
                  .map((column) => (
                    <Menu.CheckboxItem
                      key={column.id}
                      checked={column.getIsVisible()}
                      onCheckedChange={(value) => {column.toggleVisibility(value);if(closeAfterChange)setOpen(false);}}
                    >
                      {typeof column.columnDef.header === "string"
                        ? column.columnDef.header
                        : column.id}
                      <Menu.CheckboxItemIndicator>
                        {" "}
                        ✓
                      </Menu.CheckboxItemIndicator>
                    </Menu.CheckboxItem>
                  ))}
              </Menu.Popup>
            </Menu.Positioner>
          </Menu.Portal>
        </Menu.Root>;
}
export function DataTable<T>({
  data,
  columns,
  label,
  initialSorting = [],
  getRowId,
  server,
  loading = false,
  error,
  emptyMessage = "No matching records.",
  renderDetails,
  filters = [],
  toolbar,
}: {
  data: T[];
  columns: ColumnDef<T>[];
  label: string;
  initialSorting?: SortingState;
  getRowId?: (row: T) => string;
  loading?: boolean;
  error?: string;
  emptyMessage?: string;
  renderDetails?: (row: T) => ReactNode;
  filters?: { id: string; label: string; options: { value: string; label: string }[] }[];
  toolbar?: ReactNode;
  server?: {
    rowCount: number;
    pagination: PaginationState;
    sorting: SortingState;
    onPaginationChange: OnChangeFn<PaginationState>;
    onSortingChange: OnChangeFn<SortingState>;
  };
}) {
  const [filter, setFilter] = useState(""),
    [sorting, setSorting] = useState<SortingState>(initialSorting),
    [visibility, setVisibility] = useState<VisibilityState>({}),
    [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]),
    [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const tableId = useId();
  const rows = useMemo(() => data, [data]);
  const table = useReactTable({
    data: rows,
    getRowId,
    columns,
    state: {
      globalFilter: filter,
      sorting: server?.sorting ?? sorting,
      columnVisibility: visibility,
      columnFilters,
      ...(server ? { pagination: server.pagination } : {}),
    },
    onGlobalFilterChange: value => { setFilter(value); table.setPageIndex(0); },
    onColumnFiltersChange: value => { setColumnFilters(value); table.setPageIndex(0); },
    onSortingChange: server?.onSortingChange ?? setSorting,
    onPaginationChange: server?.onPaginationChange,
    autoResetPageIndex: false,
    manualPagination: !!server,
    manualSorting: !!server,
    manualFiltering: !!server,
    rowCount: server?.rowCount,
    onColumnVisibilityChange: setVisibility,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 25 } },
  });
  const pageIndex = table.getState().pagination.pageIndex;
  const pageCount = table.getPageCount();
  useEffect(() => {
    if (!loading && pageIndex > 0 && pageIndex >= pageCount) {
      table.setPageIndex(Math.max(0, pageCount - 1));
    }
  }, [loading, pageIndex, pageCount, table]);
  return (
    <div className="managed-table" aria-busy={loading}>
      <div className="managed-table-controls">
        {toolbar}
        {!server && (
          <label>
            Search {label}
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              maxLength={100}
            />
          </label>
        )}
        {!server && filters.map(({ id, label: filterLabel, options }) => <label key={id}>{filterLabel}
          <select value={String(table.getColumn(id)?.getFilterValue() ?? "")} onChange={e => table.getColumn(id)?.setFilterValue(e.target.value || undefined)}>
            <option value="">All</option>{options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </label>)}
        <ColumnMenu table={table}/>
      </div>
      <div
        className="table-scroll"
        role="region"
        aria-label={label}
        tabIndex={0}
      >
        <table aria-label={label}>
          <thead>
            {table.getHeaderGroups().map((group) => (
              <tr key={group.id}>
                {renderDetails && <th scope="col">Details</th>}
                {group.headers.map((header) => (
                  <th
                    key={header.id}
                    scope="col"
                    className={
                      (header.column.columnDef.meta as { numeric?: boolean })
                        ?.numeric
                        ? "numeric"
                        : undefined
                    }
                    aria-sort={
                      header.column.getIsSorted() === "asc"
                        ? "ascending"
                        : header.column.getIsSorted() === "desc"
                          ? "descending"
                          : "none"
                    }
                  >
                    {header.column.getCanSort() ? (
                      <button
                        className="table-sort"
                        onClick={header.column.getToggleSortingHandler()}
                      >
                        {flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )}
                        {header.column.getIsSorted() === "asc"
                          ? " ↑"
                          : header.column.getIsSorted() === "desc"
                            ? " ↓"
                            : " ↕"}
                      </button>
                    ) : (
                      flexRender(
                        header.column.columnDef.header,
                        header.getContext(),
                      )
                    )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {loading && !data.length && <tr aria-hidden="true"><td colSpan={table.getVisibleLeafColumns().length+(renderDetails?1:0)}><div className="loading-skeleton"><span/><span/><span/></div></td></tr>}
            {table.getRowModel().rows.map((row) => (
              <Fragment key={row.id}><tr>
                {renderDetails && <td><button aria-label={`${expanded[row.id] ? "Hide" : "Show"} details for ${label} ${row.id}`} aria-expanded={!!expanded[row.id]} aria-controls={`${tableId}-${row.id}`} onClick={() => setExpanded(value => ({ ...value, [row.id]: !value[row.id] }))}>{expanded[row.id] ? "−" : "+"}</button></td>}
                {row.getVisibleCells().map((cell) => (
                  <td
                    key={cell.id}
                    className={
                      (cell.column.columnDef.meta as { numeric?: boolean })
                        ?.numeric
                        ? "numeric"
                        : undefined
                    }
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
              {renderDetails && expanded[row.id] && <tr><td id={`${tableId}-${row.id}`} colSpan={row.getVisibleCells().length + 1} className="table-row-details">{renderDetails(row.original)}</td></tr>}</Fragment>
            ))}
          </tbody>
        </table>
      </div>
      {loading && <Loading label={`Loading ${label}…`} inline/>}
      {error && <p className="notice error" role="alert">{error}</p>}
      {!loading && !error && !table.getRowModel().rows.length && (
        <p className="empty">{emptyMessage}</p>
      )}
      <div className="table-pagination">
        <span aria-live="polite">
          {server?.rowCount ?? table.getFilteredRowModel().rows.length} records
          · Page {table.getState().pagination.pageIndex + 1} of{" "}
          {Math.max(1, table.getPageCount())}
        </span>
        <button
          disabled={loading || !table.getCanPreviousPage()}
          onClick={() => table.previousPage()}
        >
          Previous {label}
        </button>
        <button
          disabled={loading || !table.getCanNextPage()}
          onClick={() => table.nextPage()}
        >
          Next {label}
        </button>
        <label>Rows per page<select value={table.getState().pagination.pageSize} onChange={e => table.setPageSize(Number(e.target.value))}>{[10, 25, 50, 100].map(size => <option key={size} value={size}>{size}</option>)}</select></label>
      </div>
    </div>
  );
}
